from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from quant.analytics import BenchmarkResult
from quant.backtest import BacktestResult
from quant.domain import DatasetSnapshot, Hypothesis, MetricSet, StrategyVersion


@dataclass(frozen=True, slots=True)
class ExperimentExecutionResult:
    experiment_id: UUID
    experiment_run_id: UUID
    dataset_snapshot_id: UUID
    strategy_version_id: UUID
    hypothesis: Hypothesis
    strategy_version: StrategyVersion
    dataset_snapshot: DatasetSnapshot
    backtest_result: BacktestResult
    strategy_metrics: MetricSet
    benchmark: BenchmarkResult
    lineage: Mapping[str, object]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ReproductionResult:
    original_run_id: UUID
    original_fingerprint: str
    reproduced_fingerprint: str
    matches: bool
    mismatches: tuple[str, ...]
    backtest_result: BacktestResult
    strategy_metrics: MetricSet
    benchmark: BenchmarkResult
