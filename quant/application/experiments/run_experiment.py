from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from quant.analytics import (
    METRICS_VERSION,
    AnalyticsConfiguration,
    analyze_backtest,
    buy_and_hold_benchmark,
)
from quant.application.experiments.evidence import build_evidence, evidence_fingerprint
from quant.application.experiments.models import ExperimentExecutionResult
from quant.application.experiments.registry import (
    build_strategy,
    serialize_execution_configuration,
)
from quant.backtest import (
    BACKTEST_ENGINE_VERSION,
    BacktestConfiguration,
    BacktestEngine,
)
from quant.domain import (
    ExperimentRun,
    ExperimentRunStatus,
    HistoricalDataset,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.ports import (
    DatasetRepository,
    ExperimentRepository,
    HypothesisRepository,
    StrategyRepository,
)


class ExperimentLineageError(LookupError):
    """Raised when referenced experiment lineage cannot be resolved."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RunExperiment:
    experiments: ExperimentRepository
    hypotheses: HypothesisRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]
    run_id_factory: Callable[[], UUID] = uuid4
    validation_id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _utc_now

    def execute(
        self,
        experiment_id: UUID,
        backtest_configuration: BacktestConfiguration,
        analytics_configuration: AnalyticsConfiguration,
    ) -> ExperimentExecutionResult:
        experiment = self.experiments.get(experiment_id)
        if experiment is None:
            raise ExperimentLineageError(f"experiment {experiment_id} not found")
        hypothesis = self.hypotheses.get(experiment.hypothesis_id)
        strategy_version = self.strategies.get_version(experiment.strategy_version_id)
        snapshot = self.datasets.get(experiment.dataset_snapshot_id)
        if hypothesis is None:
            raise ExperimentLineageError("experiment hypothesis not found")
        if strategy_version is None:
            raise ExperimentLineageError("experiment strategy version not found")
        if snapshot is None:
            raise ExperimentLineageError("experiment dataset snapshot not found")

        execution_configuration = serialize_execution_configuration(
            backtest_configuration, analytics_configuration
        )
        run_id = self.run_id_factory()
        started_at = self.clock()
        running = self._run_record(
            run_id=run_id,
            experiment_id=experiment.id,
            git_commit=strategy_version.git_commit,
            execution_configuration=execution_configuration,
            started_at=started_at,
            completed_at=None,
            status=ExperimentRunStatus.RUNNING,
        )
        self.experiments.add_run(running)
        try:
            loaded = self.dataset_loader(snapshot.id)
            strategy = build_strategy(strategy_version)
            backtest_result = BacktestEngine().run(
                loaded, strategy, backtest_configuration
            )
            strategy_metrics = analyze_backtest(
                backtest_result, analytics_configuration
            )
            benchmark = buy_and_hold_benchmark(
                loaded, backtest_configuration, analytics_configuration
            )
            evidence = build_evidence(
                strategy_version=strategy_version,
                dataset_snapshot=snapshot,
                execution_configuration=execution_configuration,
                backtest_result=backtest_result,
                strategy_metrics=strategy_metrics,
                benchmark=benchmark,
            )
            fingerprint = evidence_fingerprint(evidence)
            stored_configuration: dict[str, object] = {
                "execution": execution_configuration,
                "evidence": evidence,
                "fingerprint": fingerprint,
            }
            completed_at = self.clock()
            completed = self._run_record(
                run_id=run_id,
                experiment_id=experiment.id,
                git_commit=strategy_version.git_commit,
                execution_configuration=execution_configuration,
                started_at=started_at,
                completed_at=completed_at,
                status=ExperimentRunStatus.COMPLETED,
                stored_configuration=stored_configuration,
            )
            self.experiments.save_run(completed)
            self.experiments.add_validation(
                ValidationRun(
                    id=self.validation_id_factory(),
                    experiment_run_id=run_id,
                    validation_type=ValidationType.BACKTEST,
                    status=ValidationStatus.PASSED,
                    metric_set=strategy_metrics,
                    configuration={
                        "analytics_version": METRICS_VERSION,
                        "benchmark_name": benchmark.name,
                        "benchmark_metrics": evidence["benchmark_metrics"],
                        "fingerprint": fingerprint,
                    },
                    created_at=completed_at,
                    completed_at=completed_at,
                )
            )
            return ExperimentExecutionResult(
                experiment_id=experiment.id,
                experiment_run_id=run_id,
                dataset_snapshot_id=snapshot.id,
                strategy_version_id=strategy_version.id,
                hypothesis=hypothesis,
                strategy_version=strategy_version,
                dataset_snapshot=snapshot,
                backtest_result=backtest_result,
                strategy_metrics=strategy_metrics,
                benchmark=benchmark,
                lineage=stored_configuration,
                fingerprint=fingerprint,
            )
        except Exception as error:
            failed = self._run_record(
                run_id=run_id,
                experiment_id=experiment.id,
                git_commit=strategy_version.git_commit,
                execution_configuration=execution_configuration,
                started_at=started_at,
                completed_at=self.clock(),
                status=ExperimentRunStatus.FAILED,
                stored_configuration={
                    "execution": execution_configuration,
                    "failure_reason": str(error) or type(error).__name__,
                },
            )
            self.experiments.save_run(failed)
            raise

    @staticmethod
    def _run_record(
        *,
        run_id: UUID,
        experiment_id: UUID,
        git_commit: str,
        execution_configuration: Mapping[str, object],
        started_at: datetime,
        completed_at: datetime | None,
        status: ExperimentRunStatus,
        stored_configuration: Mapping[str, object] | None = None,
    ) -> ExperimentRun:
        fee = execution_configuration["fee"]
        slippage = execution_configuration["slippage"]
        if not isinstance(fee, Mapping) or not isinstance(slippage, Mapping):
            raise ValueError("execution cost configuration is invalid")
        fee_version = fee.get("version")
        slippage_version = slippage.get("version")
        if not isinstance(fee_version, str) or not isinstance(slippage_version, str):
            raise ValueError("execution cost version is invalid")
        return ExperimentRun(
            id=run_id,
            experiment_id=experiment_id,
            git_commit=git_commit,
            engine_version=BACKTEST_ENGINE_VERSION,
            fee_model_version=fee_version,
            slippage_model_version=slippage_version,
            configuration=(
                {"execution": dict(execution_configuration)}
                if stored_configuration is None
                else stored_configuration
            ),
            started_at=started_at,
            completed_at=completed_at,
            status=status,
        )
