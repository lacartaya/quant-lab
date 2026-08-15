from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from quant.analytics import analyze_backtest, buy_and_hold_benchmark
from quant.application.experiments.evidence import (
    backtest_material,
    canonical_value,
    evidence_fingerprint,
)
from quant.application.experiments.registry import (
    build_strategy,
    build_strategy_for_parameters,
    reconstruct_configurations,
    serialize_execution_configuration,
)
from quant.backtest import (
    BacktestConfiguration,
    BacktestEngine,
    BasisPointsSlippageModel,
    PercentageFeeModel,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import (
    DatasetSnapshot,
    ExperimentRunStatus,
    HistoricalDataset,
    StrategyVersion,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.ports import DatasetRepository, ExperimentRepository, StrategyRepository
from quant.validation import (
    StressAnalysis,
    StressEvaluationScope,
    StressScenario,
    StressScenarioResult,
    StressTestingConfiguration,
    StressType,
    aggregate_stress_results,
    compare_stress_result,
)

STRESS_VALIDATION_VERSION = "stress-validation-v1"


class StressValidationLineageError(LookupError):
    """Raised when lineage required for stress validation is missing."""


@dataclass(frozen=True, slots=True)
class StressValidationResult:
    validation_run_id: UUID
    experiment_run_id: UUID
    strategy_version_id: UUID
    dataset_snapshot_id: UUID
    analysis: StressAnalysis
    fingerprint: str


@dataclass(frozen=True, slots=True)
class StressReproductionResult:
    validation_run_id: UUID
    original_fingerprint: str
    reproduced_fingerprint: str
    matches: bool
    mismatches: tuple[str, ...]
    result: StressValidationResult


@dataclass(frozen=True, slots=True)
class _ResolvedLineage:
    experiment_run_id: UUID
    strategy_version: StrategyVersion
    snapshot: DatasetSnapshot
    dataset: HistoricalDataset
    execution: Mapping[str, object]


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RunStressValidation:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]
    validation_id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _utc_now

    def execute(
        self, experiment_run_id: UUID, configuration: StressTestingConfiguration
    ) -> StressValidationResult:
        lineage = _resolve_lineage(
            experiment_run_id,
            self.experiments,
            self.strategies,
            self.datasets,
            self.dataset_loader,
        )
        validation_id = self.validation_id_factory()
        result, evidence = _evaluate(validation_id, lineage, configuration)
        now = self.clock()
        self.experiments.add_validation(
            ValidationRun(
                id=validation_id,
                experiment_run_id=experiment_run_id,
                validation_type=ValidationType.STRESS,
                status=ValidationStatus.PASSED,
                metric_set=None,
                configuration=evidence,
                created_at=now,
                completed_at=now,
            )
        )
        return result


@dataclass(frozen=True, slots=True)
class ReproduceStressValidation:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]

    def execute(self, validation_run_id: UUID) -> StressReproductionResult:
        validation = self.experiments.get_validation(validation_run_id)
        if validation is None:
            raise StressValidationLineageError("stress validation not found")
        if validation.validation_type is not ValidationType.STRESS:
            raise StressValidationLineageError("validation is not STRESS")
        if validation.status is not ValidationStatus.PASSED:
            raise StressValidationLineageError("stress validation is not completed")
        stored = _mapping(validation.configuration, "stress evidence")
        if stored.get("version") != STRESS_VALIDATION_VERSION:
            raise StressValidationLineageError("unsupported stress version")
        original_fingerprint = _text(stored, "fingerprint")
        configuration = _configuration(
            _mapping(stored.get("configuration"), "stress configuration")
        )
        lineage = _resolve_lineage(
            validation.experiment_run_id,
            self.experiments,
            self.strategies,
            self.datasets,
            self.dataset_loader,
        )
        reproduced, evidence = _evaluate(
            validation_run_id, lineage, configuration
        )
        reproduced_fingerprint = _text(evidence, "fingerprint")
        sections = (
            "lineage",
            "configuration",
            "evaluation",
            "baseline",
            "scenario_counts",
            "scenarios",
            "aggregate",
        )
        mismatches = tuple(
            section
            for section in sections
            if stored.get(section) != evidence.get(section)
        )
        if original_fingerprint != reproduced_fingerprint and not mismatches:
            mismatches = ("fingerprint",)
        return StressReproductionResult(
            validation_run_id,
            original_fingerprint,
            reproduced_fingerprint,
            not mismatches and original_fingerprint == reproduced_fingerprint,
            mismatches,
            reproduced,
        )


def _resolve_lineage(
    experiment_run_id: UUID,
    experiments: ExperimentRepository,
    strategies: StrategyRepository,
    datasets: DatasetRepository,
    dataset_loader: Callable[[UUID], HistoricalDataset],
) -> _ResolvedLineage:
    run = experiments.get_run(experiment_run_id)
    if run is None or run.status is not ExperimentRunStatus.COMPLETED:
        raise StressValidationLineageError("completed experiment run not found")
    experiment = experiments.get(run.experiment_id)
    if experiment is None:
        raise StressValidationLineageError("experiment for run not found")
    strategy_version = strategies.get_version(experiment.strategy_version_id)
    snapshot = datasets.get(experiment.dataset_snapshot_id)
    if strategy_version is None or snapshot is None:
        raise StressValidationLineageError("strategy or dataset lineage not found")
    run_configuration = _mapping(run.configuration, "experiment run configuration")
    execution = _mapping(
        run_configuration.get("execution"), "execution configuration"
    )
    return _ResolvedLineage(
        experiment_run_id,
        strategy_version,
        snapshot,
        dataset_loader(snapshot.id),
        execution,
    )


def _evaluate(
    validation_id: UUID,
    lineage: _ResolvedLineage,
    configuration: StressTestingConfiguration,
) -> tuple[StressValidationResult, dict[str, object]]:
    if (
        configuration.evaluation_scope
        is not StressEvaluationScope.FULL_HISTORY_RESEARCH
    ):
        raise ValueError("unsupported stress evaluation scope")
    baseline_configuration, analytics_configuration = reconstruct_configurations(
        lineage.execution
    )
    baseline_strategy = build_strategy(lineage.strategy_version)
    baseline_backtest = BacktestEngine().run(
        lineage.dataset, baseline_strategy, baseline_configuration
    )
    baseline_metrics = analyze_backtest(baseline_backtest, analytics_configuration)
    baseline_benchmark = buy_and_hold_benchmark(
        lineage.dataset, baseline_configuration, analytics_configuration
    )
    scenario_results: list[StressScenarioResult] = []
    for scenario in configuration.scenarios:
        stressed_configuration, delay, parameters, no_effect = apply_stress_scenario(
            scenario, baseline_configuration, lineage.strategy_version
        )
        strategy = (
            build_strategy(lineage.strategy_version)
            if parameters is None
            else build_strategy_for_parameters(lineage.strategy_version, parameters)
        )
        backtest = BacktestEngine().run(
            lineage.dataset,
            strategy,
            stressed_configuration,
            execution_delay_bars=delay,
        )
        metrics = analyze_backtest(backtest, analytics_configuration)
        shared_execution_stress = scenario.stress_type in (
            StressType.FEE_MULTIPLIER,
            StressType.SLIPPAGE_MULTIPLIER,
            StressType.ADVERSE_PRICE,
        )
        benchmark = (
            buy_and_hold_benchmark(
                lineage.dataset, stressed_configuration, analytics_configuration
            )
            if shared_execution_stress
            else baseline_benchmark
        )
        scenario_results.append(
            StressScenarioResult(
                scenario,
                {
                    "execution": serialize_execution_configuration(
                        stressed_configuration, analytics_configuration
                    ),
                    "execution_delay_bars": delay,
                    "strategy_parameters": (
                        dict(lineage.strategy_version.parameters)
                        if parameters is None
                        else dict(parameters)
                    ),
                },
                no_effect,
                backtest,
                metrics,
                compare_stress_result(
                    baseline_backtest, baseline_metrics, backtest, metrics
                ),
                benchmark,
            )
        )
    results = tuple(scenario_results)
    aggregate = aggregate_stress_results(results, baseline_metrics)
    analysis = StressAnalysis(
        configuration,
        baseline_backtest,
        baseline_metrics,
        baseline_benchmark,
        results,
        aggregate,
    )
    material: dict[str, object] = {
        "lineage": {
            "experiment_run_id": str(lineage.experiment_run_id),
            "strategy_version_id": str(lineage.strategy_version.id),
            "algorithm_key": lineage.strategy_version.algorithm_key,
            "parameters": canonical_value(lineage.strategy_version.parameters),
            "git_commit": lineage.strategy_version.git_commit,
            "dataset_snapshot_id": str(lineage.snapshot.id),
            "dataset_checksum": lineage.snapshot.checksum,
            "execution": canonical_value(lineage.execution),
        },
        "configuration": canonical_value(configuration),
        "evaluation": {
            "scope": configuration.evaluation_scope.value,
            "start": canonical_value(lineage.dataset.bars[0].timestamp),
            "end": canonical_value(lineage.dataset.bars[-1].timestamp),
            "contaminates_future_oos_interpretation": True,
        },
        "baseline": {
            "backtest": backtest_material(baseline_backtest),
            "metrics": canonical_value(baseline_metrics),
            "benchmark": _benchmark_evidence(baseline_benchmark),
        },
        "scenario_counts": {
            "requested": len(configuration.scenarios),
            "executed": len(results),
            "failed": 0,
        },
        "scenarios": [_scenario_evidence(item) for item in results],
        "aggregate": canonical_value(aggregate),
    }
    fingerprint = evidence_fingerprint(material)
    evidence = {
        "version": STRESS_VALIDATION_VERSION,
        **material,
        "fingerprint": fingerprint,
    }
    return (
        StressValidationResult(
            validation_id,
            lineage.experiment_run_id,
            lineage.strategy_version.id,
            lineage.snapshot.id,
            analysis,
            fingerprint,
        ),
        evidence,
    )


def apply_stress_scenario(
    scenario: StressScenario,
    baseline: BacktestConfiguration,
    strategy_version: StrategyVersion,
) -> tuple[BacktestConfiguration, int, Mapping[str, object] | None, bool]:
    fee_model = baseline.fee_model
    slippage_model = baseline.slippage_model
    delay = 0
    parameters: Mapping[str, object] | None = None
    no_effect = False
    if scenario.stress_type is StressType.FEE_MULTIPLIER:
        multiplier = _decimal(scenario.configuration, "multiplier")
        if isinstance(fee_model, ZeroFeeModel):
            no_effect = True
        elif isinstance(fee_model, PercentageFeeModel):
            fee_model = PercentageFeeModel(fee_model.rate * multiplier)
        else:
            raise ValueError("unsupported baseline fee model")
    elif scenario.stress_type is StressType.SLIPPAGE_MULTIPLIER:
        multiplier = _decimal(scenario.configuration, "multiplier")
        if isinstance(slippage_model, ZeroSlippageModel):
            no_effect = True
        elif isinstance(slippage_model, BasisPointsSlippageModel):
            slippage_model = BasisPointsSlippageModel(
                slippage_model.basis_points * multiplier
            )
        else:
            raise ValueError("unsupported baseline slippage model")
    elif scenario.stress_type is StressType.ADVERSE_PRICE:
        additional = _decimal(scenario.configuration, "additional_basis_points")
        baseline_points = (
            Decimal(0)
            if isinstance(slippage_model, ZeroSlippageModel)
            else slippage_model.basis_points
            if isinstance(slippage_model, BasisPointsSlippageModel)
            else None
        )
        if baseline_points is None:
            raise ValueError("unsupported baseline slippage model")
        slippage_model = BasisPointsSlippageModel(baseline_points + additional)
        no_effect = additional == 0
    elif scenario.stress_type is StressType.EXECUTION_DELAY:
        delay = _integer(scenario.configuration, "additional_delay_bars")
        no_effect = delay == 0
    elif scenario.stress_type is StressType.PARAMETER_PERTURBATION:
        parameters = _mapping(
            scenario.configuration.get("parameters"), "stress parameters"
        )
        no_effect = dict(parameters) == dict(strategy_version.parameters)
    return (
        BacktestConfiguration(
            baseline.initial_cash,
            baseline.position_fraction,
            fee_model,
            slippage_model,
        ),
        delay,
        parameters,
        no_effect,
    )


def _scenario_evidence(result: StressScenarioResult) -> dict[str, object]:
    return {
        "scenario": canonical_value(result.scenario),
        "effective_configuration": canonical_value(result.effective_configuration),
        "no_effect": result.no_effect,
        "backtest": backtest_material(result.backtest_result),
        "metrics": canonical_value(result.metrics),
        "comparison": canonical_value(result.comparison),
        "benchmark": _benchmark_evidence(result.benchmark),
    }


def _benchmark_evidence(benchmark: object) -> dict[str, object]:
    from quant.analytics import BenchmarkResult

    if not isinstance(benchmark, BenchmarkResult):
        raise TypeError("benchmark result is invalid")
    return {
        "name": benchmark.name,
        "metrics": canonical_value(benchmark.metrics),
        "backtest": backtest_material(benchmark.backtest_result),
    }


def _configuration(values: Mapping[str, object]) -> StressTestingConfiguration:
    raw_scenarios = values.get("scenarios")
    if not isinstance(raw_scenarios, list):
        raise StressValidationLineageError("stress scenarios are missing")
    scenarios = tuple(_scenario(item) for item in raw_scenarios)
    try:
        return StressTestingConfiguration(
            scenarios,
            StressEvaluationScope(_text(values, "evaluation_scope")),
        )
    except ValueError as error:
        raise StressValidationLineageError("invalid stress configuration") from error


def _scenario(value: object) -> StressScenario:
    values = _mapping(value, "stress scenario")
    stress_type = StressType(_text(values, "stress_type"))
    raw_configuration = _mapping(
        values.get("configuration"), "scenario configuration"
    )
    configuration: dict[str, object] = dict(raw_configuration)
    for decimal_name in ("multiplier", "additional_basis_points"):
        raw_decimal = configuration.get(decimal_name)
        if isinstance(raw_decimal, str):
            configuration[decimal_name] = Decimal(raw_decimal)
    return StressScenario(
        _text(values, "id"),
        _text(values, "name"),
        stress_type,
        configuration,
    )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StressValidationLineageError(f"{name} is missing")
    return value


def _text(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise StressValidationLineageError(f"{name} is missing")
    return value


def _integer(values: Mapping[str, object], name: str) -> int:
    value = values.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise StressValidationLineageError(f"{name} is missing")
    return value


def _decimal(values: Mapping[str, object], name: str) -> Decimal:
    value = values.get(name)
    if not isinstance(value, Decimal):
        raise StressValidationLineageError(f"{name} is missing")
    return value
