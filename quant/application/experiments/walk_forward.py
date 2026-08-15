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
    build_strategy,
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
    WalkForwardAggregate,
    WalkForwardConfiguration,
    WalkForwardFold,
    WalkForwardFoldResult,
    WalkForwardMode,
    aggregate_walk_forward,
    generate_walk_forward_folds,
)

WALK_FORWARD_VERSION = "walk-forward-v1"


class WalkForwardLineageError(LookupError):
    """Raised when lineage needed for walk-forward validation is missing."""


@dataclass(frozen=True, slots=True)
class WalkForwardValidationResult:
    validation_run_id: UUID
    experiment_run_id: UUID
    strategy_version_id: UUID
    dataset_snapshot_id: UUID
    configuration: WalkForwardConfiguration
    fold_results: tuple[WalkForwardFoldResult, ...]
    aggregate: WalkForwardAggregate
    fingerprint: str


@dataclass(frozen=True, slots=True)
class WalkForwardReproductionResult:
    validation_run_id: UUID
    original_fingerprint: str
    reproduced_fingerprint: str
    matches: bool
    mismatches: tuple[str, ...]
    result: WalkForwardValidationResult


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
class RunWalkForwardValidation:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]
    validation_id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _utc_now

    def execute(
        self,
        experiment_run_id: UUID,
        configuration: WalkForwardConfiguration,
    ) -> WalkForwardValidationResult:
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
                validation_type=ValidationType.WALK_FORWARD,
                status=ValidationStatus.PASSED,
                metric_set=None,
                configuration=evidence,
                created_at=now,
                completed_at=now,
            )
        )
        return result


@dataclass(frozen=True, slots=True)
class ReproduceWalkForwardValidation:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]

    def execute(self, validation_run_id: UUID) -> WalkForwardReproductionResult:
        validation = self.experiments.get_validation(validation_run_id)
        if validation is None:
            raise WalkForwardLineageError(
                f"validation run {validation_run_id} not found"
            )
        if validation.validation_type is not ValidationType.WALK_FORWARD:
            raise WalkForwardLineageError("validation is not WALK_FORWARD")
        if validation.status is not ValidationStatus.PASSED:
            raise WalkForwardLineageError("walk-forward validation is not completed")
        stored = _mapping(validation.configuration, "walk-forward evidence")
        if stored.get("version") != WALK_FORWARD_VERSION:
            raise WalkForwardLineageError("unsupported walk-forward version")
        original_fingerprint = _text(stored, "fingerprint")
        configuration = _configuration(
            _mapping(stored.get("configuration"), "walk-forward configuration")
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
        mismatches = tuple(
            section
            for section in (
                "lineage",
                "configuration",
                "warmup_policy",
                "capital_convention",
                "benchmark",
                "folds",
                "aggregate",
            )
            if stored.get(section) != evidence.get(section)
        )
        if original_fingerprint != reproduced_fingerprint and not mismatches:
            mismatches = ("fingerprint",)
        return WalkForwardReproductionResult(
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
        raise WalkForwardLineageError("completed experiment run not found")
    experiment = experiments.get(run.experiment_id)
    if experiment is None:
        raise WalkForwardLineageError("experiment for run not found")
    strategy_version = strategies.get_version(experiment.strategy_version_id)
    snapshot = datasets.get(experiment.dataset_snapshot_id)
    if strategy_version is None or snapshot is None:
        raise WalkForwardLineageError("strategy or dataset lineage not found")
    stored_run = _mapping(run.configuration, "experiment run configuration")
    execution = _mapping(stored_run.get("execution"), "execution configuration")
    return _ResolvedLineage(
        experiment_run_id=experiment_run_id,
        strategy_version=strategy_version,
        snapshot=snapshot,
        dataset=dataset_loader(snapshot.id),
        execution=execution,
    )


def _evaluate(
    validation_id: UUID,
    lineage: _ResolvedLineage,
    configuration: WalkForwardConfiguration,
) -> tuple[WalkForwardValidationResult, dict[str, object]]:
    backtest_configuration, analytics_configuration = reconstruct_configurations(
        lineage.execution
    )
    folds = generate_walk_forward_folds(lineage.dataset, configuration)
    results: list[WalkForwardFoldResult] = []
    for fold in folds:
        context = _slice_dataset(lineage.dataset, fold)
        test = HistoricalDataset.from_bars(
            market=lineage.dataset.market,
            instrument=lineage.dataset.instrument,
            timeframe=lineage.dataset.timeframe,
            adjustment_policy=lineage.dataset.adjustment_policy,
            bars=lineage.dataset.bars[fold.test_start_index : fold.test_end_index + 1],
            metadata=lineage.dataset.metadata,
        )
        strategy = build_strategy(lineage.strategy_version)
        backtest = BacktestEngine().run(
            context,
            strategy,
            backtest_configuration,
            evaluation_start=fold.test_start,
        )
        metrics = analyze_backtest(backtest, analytics_configuration)
        benchmark = buy_and_hold_benchmark(
            test, backtest_configuration, analytics_configuration
        )
        strategy_return = _required(metrics.total_return)
        benchmark_return = _required(benchmark.metrics.total_return)
        results.append(
            WalkForwardFoldResult(
                fold=fold,
                strategy_version_id=str(lineage.strategy_version.id),
                backtest_result=backtest,
                strategy_metrics=metrics,
                benchmark=benchmark,
                excess_total_return=strategy_return - benchmark_return,
            )
        )
    fold_results = tuple(results)
    aggregate = aggregate_walk_forward(fold_results)
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
        "warmup_policy": "pre-test-history-signals-only",
        "capital_convention": "independent-per-fold",
        "benchmark": "BUY_AND_HOLD",
        "folds": [_fold_evidence(item) for item in fold_results],
        "aggregate": canonical_value(aggregate),
    }
    fingerprint = evidence_fingerprint(material)
    evidence = {
        "version": WALK_FORWARD_VERSION,
        **material,
        "fingerprint": fingerprint,
    }
    return (
        WalkForwardValidationResult(
            validation_run_id=validation_id,
            experiment_run_id=lineage.experiment_run_id,
            strategy_version_id=lineage.strategy_version.id,
            dataset_snapshot_id=lineage.snapshot.id,
            configuration=configuration,
            fold_results=fold_results,
            aggregate=aggregate,
            fingerprint=fingerprint,
        ),
        evidence,
    )


def _slice_dataset(
    dataset: HistoricalDataset, fold: WalkForwardFold
) -> HistoricalDataset:
    return HistoricalDataset.from_bars(
        market=dataset.market,
        instrument=dataset.instrument,
        timeframe=dataset.timeframe,
        adjustment_policy=dataset.adjustment_policy,
        bars=dataset.bars[fold.training_start_index : fold.test_end_index + 1],
        metadata=dataset.metadata,
    )


def _fold_evidence(result: WalkForwardFoldResult) -> dict[str, object]:
    return {
        "id": result.fold.id,
        "fold": canonical_value(result.fold),
        "strategy_version_id": result.strategy_version_id,
        "backtest": backtest_material(result.backtest_result),
        "strategy_metrics": canonical_value(result.strategy_metrics),
        "benchmark_name": result.benchmark.name,
        "benchmark_backtest": backtest_material(result.benchmark.backtest_result),
        "benchmark_metrics": canonical_value(result.benchmark.metrics),
        "excess_total_return": result.excess_total_return,
    }


def _configuration(values: Mapping[str, object]) -> WalkForwardConfiguration:
    try:
        return WalkForwardConfiguration(
            mode=WalkForwardMode(_text(values, "mode")),
            training_window=_integer(values, "training_window"),
            test_window=_integer(values, "test_window"),
            step=_integer(values, "step"),
        )
    except ValueError as error:
        raise WalkForwardLineageError("invalid walk-forward configuration") from error


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise WalkForwardLineageError(f"{name} is missing")
    return value


def _text(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise WalkForwardLineageError(f"{name} is missing")
    return value


def _integer(values: Mapping[str, object], name: str) -> int:
    value = values.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise WalkForwardLineageError(f"{name} is missing")
    return value


def _required(value: float | None) -> float:
    if value is None:
        raise ValueError("total return is required")
    return value
