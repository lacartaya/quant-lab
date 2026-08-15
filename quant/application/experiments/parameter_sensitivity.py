from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from quant.analytics import analyze_backtest, buy_and_hold_benchmark
from quant.application.experiments.evidence import (
    backtest_material,
    canonical_value,
    evidence_fingerprint,
)
from quant.application.experiments.registry import (
    build_strategy_for_parameters,
    reconstruct_configurations,
)
from quant.backtest import BacktestEngine
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
    ParameterCandidateResult,
    ParameterSensitivityAnalysis,
    ParameterSensitivityConfiguration,
    SensitivityEvaluationScope,
    generate_parameter_combinations,
    relative_parameter_distance,
    summarize_parameter_sensitivity,
)

PARAMETER_SENSITIVITY_VERSION = "parameter-sensitivity-v1"


class ParameterSensitivityLineageError(LookupError):
    """Raised when persisted sensitivity lineage cannot be resolved."""


@dataclass(frozen=True, slots=True)
class ParameterSensitivityValidationResult:
    validation_run_id: UUID
    experiment_run_id: UUID
    strategy_version_id: UUID
    dataset_snapshot_id: UUID
    analysis: ParameterSensitivityAnalysis
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ParameterSensitivityReproductionResult:
    validation_run_id: UUID
    original_fingerprint: str
    reproduced_fingerprint: str
    matches: bool
    mismatches: tuple[str, ...]
    result: ParameterSensitivityValidationResult


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
class RunParameterSensitivityValidation:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]
    validation_id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _utc_now

    def execute(
        self,
        experiment_run_id: UUID,
        configuration: ParameterSensitivityConfiguration,
    ) -> ParameterSensitivityValidationResult:
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
                validation_type=ValidationType.PARAMETER_SENSITIVITY,
                status=ValidationStatus.PASSED,
                metric_set=None,
                configuration=evidence,
                created_at=now,
                completed_at=now,
            )
        )
        return result


@dataclass(frozen=True, slots=True)
class ReproduceParameterSensitivityValidation:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]

    def execute(
        self, validation_run_id: UUID
    ) -> ParameterSensitivityReproductionResult:
        validation = self.experiments.get_validation(validation_run_id)
        if validation is None:
            raise ParameterSensitivityLineageError("sensitivity validation not found")
        if validation.validation_type is not ValidationType.PARAMETER_SENSITIVITY:
            raise ParameterSensitivityLineageError(
                "validation is not PARAMETER_SENSITIVITY"
            )
        if validation.status is not ValidationStatus.PASSED:
            raise ParameterSensitivityLineageError(
                "parameter sensitivity validation is not completed"
            )
        stored = _mapping(validation.configuration, "sensitivity evidence")
        if stored.get("version") != PARAMETER_SENSITIVITY_VERSION:
            raise ParameterSensitivityLineageError(
                "unsupported parameter sensitivity version"
            )
        original_fingerprint = _text(stored, "fingerprint")
        configuration = _configuration(
            _mapping(stored.get("configuration"), "sensitivity configuration")
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
            "search_counts",
            "baseline",
            "candidates",
            "summary",
            "benchmark",
        )
        mismatches = tuple(
            section
            for section in sections
            if stored.get(section) != evidence.get(section)
        )
        if original_fingerprint != reproduced_fingerprint and not mismatches:
            mismatches = ("fingerprint",)
        return ParameterSensitivityReproductionResult(
            validation_run_id=validation_run_id,
            original_fingerprint=original_fingerprint,
            reproduced_fingerprint=reproduced_fingerprint,
            matches=(
                not mismatches and original_fingerprint == reproduced_fingerprint
            ),
            mismatches=mismatches,
            result=reproduced,
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
        raise ParameterSensitivityLineageError("completed experiment run not found")
    experiment = experiments.get(run.experiment_id)
    if experiment is None:
        raise ParameterSensitivityLineageError("experiment for run not found")
    strategy_version = strategies.get_version(experiment.strategy_version_id)
    snapshot = datasets.get(experiment.dataset_snapshot_id)
    if strategy_version is None or snapshot is None:
        raise ParameterSensitivityLineageError("strategy or dataset lineage not found")
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
    configuration: ParameterSensitivityConfiguration,
) -> tuple[ParameterSensitivityValidationResult, dict[str, object]]:
    if (
        configuration.evaluation_scope
        is not SensitivityEvaluationScope.FULL_HISTORY_RESEARCH
    ):
        raise ValueError("unsupported sensitivity evaluation scope")
    space = generate_parameter_combinations(
        configuration, lineage.strategy_version.parameters
    )
    backtest_configuration, analytics_configuration = reconstruct_configurations(
        lineage.execution
    )
    baseline_parameters = {
        "short_window": _integer(lineage.strategy_version.parameters, "short_window"),
        "long_window": _integer(lineage.strategy_version.parameters, "long_window"),
    }
    candidates: list[ParameterCandidateResult] = []
    for combination in space.combinations:
        strategy = build_strategy_for_parameters(
            lineage.strategy_version, combination.values
        )
        backtest = BacktestEngine().run(
            lineage.dataset, strategy, backtest_configuration
        )
        candidates.append(
            ParameterCandidateResult(
                combination=combination,
                metrics=analyze_backtest(backtest, analytics_configuration),
                backtest_result=backtest,
                relative_distance=relative_parameter_distance(
                    combination.values, baseline_parameters
                ),
            )
        )
    candidate_results = tuple(candidates)
    baseline = next(
        result for result in candidate_results if result.combination.is_baseline
    )
    benchmark = buy_and_hold_benchmark(
        lineage.dataset, backtest_configuration, analytics_configuration
    )
    summary = summarize_parameter_sensitivity(
        space, candidate_results, configuration
    )
    analysis = ParameterSensitivityAnalysis(
        configuration,
        baseline_parameters,
        baseline.metrics,
        candidate_results,
        benchmark,
        summary,
    )
    material: dict[str, object] = {
        "lineage": {
            "experiment_run_id": str(lineage.experiment_run_id),
            "strategy_version_id": str(lineage.strategy_version.id),
            "algorithm_key": lineage.strategy_version.algorithm_key,
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
        "search_counts": {
            "requested": space.requested_count,
            "executed": len(candidate_results),
            "invalid": space.invalid_count,
            "baseline_added": space.baseline_added,
        },
        "baseline": {
            "parameters": canonical_value(baseline_parameters),
            "metrics": canonical_value(baseline.metrics),
        },
        "candidates": [_candidate_evidence(item) for item in candidate_results],
        "summary": canonical_value(summary),
        "benchmark": {
            "name": benchmark.name,
            "metrics": canonical_value(benchmark.metrics),
            "backtest": backtest_material(benchmark.backtest_result),
        },
    }
    fingerprint = evidence_fingerprint(material)
    evidence = {
        "version": PARAMETER_SENSITIVITY_VERSION,
        **material,
        "fingerprint": fingerprint,
    }
    return (
        ParameterSensitivityValidationResult(
            validation_id,
            lineage.experiment_run_id,
            lineage.strategy_version.id,
            lineage.snapshot.id,
            analysis,
            fingerprint,
        ),
        evidence,
    )


def _candidate_evidence(result: ParameterCandidateResult) -> dict[str, object]:
    return {
        "id": result.combination.id,
        "parameters": canonical_value(result.combination.values),
        "is_baseline": result.combination.is_baseline,
        "relative_distance": canonical_value(result.relative_distance),
        "metrics": canonical_value(result.metrics),
        "backtest": backtest_material(result.backtest_result),
    }


def _configuration(
    values: Mapping[str, object],
) -> ParameterSensitivityConfiguration:
    parameters = _mapping(values.get("parameters"), "parameter grid")
    parsed: dict[str, tuple[int, ...]] = {}
    for name, raw_values in parameters.items():
        if not isinstance(raw_values, list):
            raise ParameterSensitivityLineageError("parameter values are invalid")
        parsed[name] = tuple(_list_integer(item, name) for item in raw_values)
    try:
        return ParameterSensitivityConfiguration(
            parameters=parsed,
            maximum_combinations=_integer(values, "maximum_combinations"),
            evaluation_scope=SensitivityEvaluationScope(
                _text(values, "evaluation_scope")
            ),
        )
    except ValueError as error:
        raise ParameterSensitivityLineageError(
            "invalid sensitivity configuration"
        ) from error


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ParameterSensitivityLineageError(f"{name} is missing")
    return value


def _text(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise ParameterSensitivityLineageError(f"{name} is missing")
    return value


def _integer(values: Mapping[str, object], name: str) -> int:
    value = values.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ParameterSensitivityLineageError(f"{name} is missing")
    return value


def _list_integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ParameterSensitivityLineageError(f"{name} contains non-integers")
    return value
