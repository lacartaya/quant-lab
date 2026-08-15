from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from quant.analytics import METRICS_VERSION, analyze_backtest, buy_and_hold_benchmark
from quant.application.experiments.evidence import build_evidence, evidence_fingerprint
from quant.application.experiments.models import ReproductionResult
from quant.application.experiments.registry import (
    UnsupportedVersionError,
    build_strategy,
    reconstruct_configurations,
    resolve_analytics,
    resolve_engine,
)
from quant.domain import (
    ExperimentRunStatus,
    HistoricalDataset,
    ValidationStatus,
    ValidationType,
)
from quant.ports import DatasetRepository, ExperimentRepository, StrategyRepository


class ReproductionLineageError(LookupError):
    """Raised when persisted evidence required for reproduction is absent."""


@dataclass(frozen=True, slots=True)
class ReproduceExperiment:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]

    def execute(self, run_id: UUID) -> ReproductionResult:
        original_run = self.experiments.get_run(run_id)
        if original_run is None:
            raise ReproductionLineageError(f"experiment run {run_id} not found")
        if original_run.status is not ExperimentRunStatus.COMPLETED:
            raise ReproductionLineageError(
                "only completed experiment runs can reproduce"
            )
        experiment = self.experiments.get(original_run.experiment_id)
        if experiment is None:
            raise ReproductionLineageError("experiment for run not found")
        strategy_version = self.strategies.get_version(experiment.strategy_version_id)
        snapshot = self.datasets.get(experiment.dataset_snapshot_id)
        if strategy_version is None:
            raise ReproductionLineageError("strategy version for run not found")
        if snapshot is None:
            raise ReproductionLineageError("dataset snapshot for run not found")

        stored = _mapping(original_run.configuration, "run")
        execution = _mapping(stored.get("execution"), "execution")
        original_evidence = _mapping(stored.get("evidence"), "evidence")
        original_fingerprint = _text(stored, "fingerprint")
        engine_version = _text(execution, "engine_version")
        resolve_engine(engine_version)
        backtest_configuration, analytics_configuration = reconstruct_configurations(
            execution
        )
        analytics_values = _mapping(execution.get("analytics"), "analytics")
        analytics_version = _text(analytics_values, "version")
        resolve_analytics(analytics_version)
        self._validate_record_versions(original_run, execution)
        self._validate_validation(run_id, original_evidence)

        dataset = self.dataset_loader(snapshot.id)
        strategy = build_strategy(strategy_version)
        backtest_result = resolve_engine(engine_version).run(
            dataset, strategy, backtest_configuration
        )
        strategy_metrics = analyze_backtest(backtest_result, analytics_configuration)
        benchmark = buy_and_hold_benchmark(
            dataset, backtest_configuration, analytics_configuration
        )
        reproduced_evidence = build_evidence(
            strategy_version=strategy_version,
            dataset_snapshot=snapshot,
            execution_configuration=execution,
            backtest_result=backtest_result,
            strategy_metrics=strategy_metrics,
            benchmark=benchmark,
        )
        reproduced_fingerprint = evidence_fingerprint(reproduced_evidence)
        mismatches = _material_mismatches(original_evidence, reproduced_evidence)
        if reproduced_fingerprint != original_fingerprint and not mismatches:
            mismatches = ("fingerprint",)
        return ReproductionResult(
            original_run_id=run_id,
            original_fingerprint=original_fingerprint,
            reproduced_fingerprint=reproduced_fingerprint,
            matches=(not mismatches and reproduced_fingerprint == original_fingerprint),
            mismatches=mismatches,
            backtest_result=backtest_result,
            strategy_metrics=strategy_metrics,
            benchmark=benchmark,
        )

    def _validate_validation(
        self, run_id: UUID, original_evidence: Mapping[str, object]
    ) -> None:
        validations = [
            item
            for item in self.experiments.list_validations(run_id)
            if item.validation_type is ValidationType.BACKTEST
        ]
        if len(validations) != 1:
            raise ReproductionLineageError("run must have one BACKTEST validation")
        validation = validations[0]
        if (
            validation.status is not ValidationStatus.PASSED
            or validation.metric_set is None
        ):
            raise ReproductionLineageError("BACKTEST validation is not completed")
        analytics_version = validation.configuration.get("analytics_version")
        if analytics_version != METRICS_VERSION:
            raise UnsupportedVersionError(
                f"unsupported analytics version: {analytics_version}"
            )
        from quant.application.experiments.evidence import canonical_value

        if canonical_value(validation.metric_set) != original_evidence.get(
            "strategy_metrics"
        ):
            raise ReproductionLineageError(
                "validation metrics do not match stored experiment evidence"
            )

    @staticmethod
    def _validate_record_versions(
        original_run: object, execution: Mapping[str, object]
    ) -> None:
        from quant.domain import ExperimentRun

        if not isinstance(original_run, ExperimentRun):
            raise TypeError("invalid experiment run")
        fee = _mapping(execution.get("fee"), "fee")
        slippage = _mapping(execution.get("slippage"), "slippage")
        if original_run.engine_version != execution.get("engine_version"):
            raise ReproductionLineageError("engine version lineage is inconsistent")
        if original_run.fee_model_version != fee.get("version"):
            raise ReproductionLineageError("fee model lineage is inconsistent")
        if original_run.slippage_model_version != slippage.get("version"):
            raise ReproductionLineageError("slippage model lineage is inconsistent")


def _material_mismatches(
    original: Mapping[str, object], reproduced: Mapping[str, object]
) -> tuple[str, ...]:
    mismatches: list[str] = []
    for section in (
        "lineage",
        "strategy_metrics",
        "benchmark_name",
        "benchmark_metrics",
        "benchmark_backtest",
    ):
        if original.get(section) != reproduced.get(section):
            mismatches.append(section)
    original_backtest = _mapping(original.get("backtest"), "backtest evidence")
    reproduced_backtest = _mapping(reproduced.get("backtest"), "backtest evidence")
    for section in (
        "final_cash",
        "final_equity",
        "orders",
        "fills",
        "trades",
        "equity_curve",
        "open_position",
    ):
        if original_backtest.get(section) != reproduced_backtest.get(section):
            mismatches.append(f"backtest.{section}")
    return tuple(mismatches)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReproductionLineageError(f"{name} lineage is missing")
    return value


def _text(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise ReproductionLineageError(f"{name} lineage is missing")
    return value
