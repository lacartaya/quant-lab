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
    ExperimentRunStatus,
    HistoricalDataset,
    MetricSet,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.ports import DatasetRepository, ExperimentRepository, StrategyRepository
from quant.validation.out_of_sample import OutOfSampleConfiguration

OUT_OF_SAMPLE_VERSION = "out-of-sample-v1"


class OutOfSampleLineageError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class OutOfSampleValidationResult:
    validation_run_id: UUID
    metrics: MetricSet
    fingerprint: str


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RunOutOfSampleValidation:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]
    validation_id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _now

    def execute(
        self, run_id: UUID, configuration: OutOfSampleConfiguration
    ) -> OutOfSampleValidationResult:
        run = self.experiments.get_run(run_id)
        if run is None or run.status is not ExperimentRunStatus.COMPLETED:
            raise OutOfSampleLineageError("completed experiment run not found")
        experiment = self.experiments.get(run.experiment_id)
        if experiment is None:
            raise OutOfSampleLineageError("experiment lineage not found")
        version = self.strategies.get_version(experiment.strategy_version_id)
        snapshot = self.datasets.get(experiment.dataset_snapshot_id)
        if version is None or snapshot is None:
            raise OutOfSampleLineageError("strategy or dataset lineage not found")
        dataset = self.dataset_loader(snapshot.id)
        training = tuple(
            bar
            for bar in dataset.bars
            if configuration.training_start
            <= bar.timestamp
            <= configuration.training_end
        )
        test = tuple(
            bar
            for bar in dataset.bars
            if configuration.test_start <= bar.timestamp <= configuration.test_end
        )
        if not training or not test:
            raise ValueError("OOS ranges must each contain at least one bar")
        if training[-1].timestamp >= test[0].timestamp:
            raise ValueError("OOS training bars must strictly precede test bars")
        context = HistoricalDataset.from_bars(
            market=dataset.market,
            instrument=dataset.instrument,
            timeframe=dataset.timeframe,
            adjustment_policy=dataset.adjustment_policy,
            bars=training + test,
            metadata=dataset.metadata,
        )
        test_dataset = HistoricalDataset.from_bars(
            market=dataset.market,
            instrument=dataset.instrument,
            timeframe=dataset.timeframe,
            adjustment_policy=dataset.adjustment_policy,
            bars=test,
            metadata=dataset.metadata,
        )
        stored = _mapping(run.configuration, "experiment run configuration")
        execution = _mapping(stored.get("execution"), "execution configuration")
        backtest_configuration, analytics_configuration = reconstruct_configurations(
            execution
        )
        result = BacktestEngine().run(
            context,
            build_strategy(version),
            backtest_configuration,
            evaluation_start=test[0].timestamp,
        )
        metrics = analyze_backtest(result, analytics_configuration)
        benchmark = buy_and_hold_benchmark(
            test_dataset, backtest_configuration, analytics_configuration
        )
        material: dict[str, object] = {
            "lineage": {
                "experiment_run_id": str(run.id),
                "strategy_version_id": str(version.id),
                "dataset_snapshot_id": str(snapshot.id),
                "dataset_checksum": snapshot.checksum,
                "execution": canonical_value(execution),
            },
            "configuration": canonical_value(configuration),
            "temporal_separation": canonical_value(
                {
                    "training_last_bar": training[-1].timestamp,
                    "test_first_bar": test[0].timestamp,
                    "training_bar_count": len(training),
                    "test_bar_count": len(test),
                    "test_data_used_for_training": False,
                }
            ),
            "warmup_policy": "training-bars-are-signal-context-only",
            "backtest": backtest_material(result),
            "metrics": canonical_value(metrics),
            "benchmark_name": benchmark.name,
            "benchmark_backtest": backtest_material(benchmark.backtest_result),
            "benchmark_metrics": canonical_value(benchmark.metrics),
        }
        fingerprint = evidence_fingerprint(material)
        evidence = {
            "version": OUT_OF_SAMPLE_VERSION,
            **material,
            "fingerprint": fingerprint,
        }
        validation_id = self.validation_id_factory()
        now = self.clock()
        self.experiments.add_validation(
            ValidationRun(
                validation_id,
                run.id,
                ValidationType.OUT_OF_SAMPLE,
                ValidationStatus.PASSED,
                metrics,
                evidence,
                now,
                now,
            )
        )
        return OutOfSampleValidationResult(validation_id, metrics, fingerprint)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise OutOfSampleLineageError(f"{name} is missing")
    return value
