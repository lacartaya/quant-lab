from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from statistics import fmean, median, pstdev

from quant.analytics import BenchmarkResult
from quant.backtest import BacktestResult
from quant.domain import HistoricalDataset, MetricSet


class WalkForwardMode(StrEnum):
    EXPANDING = "expanding"
    ROLLING = "rolling"


@dataclass(frozen=True, slots=True)
class WalkForwardConfiguration:
    mode: WalkForwardMode
    training_window: int
    test_window: int
    step: int

    def __post_init__(self) -> None:
        for name in ("training_window", "test_window", "step"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.step < self.test_window:
            raise ValueError("step must be at least test_window")


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    index: int
    training_start: datetime
    training_end: datetime
    test_start: datetime
    test_end: datetime
    warmup_start: datetime
    training_start_index: int
    test_start_index: int
    test_end_index: int

    @property
    def id(self) -> str:
        return f"FOLD-{self.index:03d}"


@dataclass(frozen=True, slots=True)
class WalkForwardFoldResult:
    fold: WalkForwardFold
    strategy_version_id: str
    backtest_result: BacktestResult
    strategy_metrics: MetricSet
    benchmark: BenchmarkResult
    excess_total_return: float


@dataclass(frozen=True, slots=True)
class WalkForwardAggregate:
    fold_count: int
    profitable_fold_count: int
    profitable_fold_ratio: float
    mean_total_return: float
    median_total_return: float
    return_std_across_folds: float
    mean_sharpe: float | None
    median_sharpe: float | None
    sharpe_std_across_folds: float | None
    worst_max_drawdown: float | None
    median_trade_count: float | None
    benchmark_outperformance_count: int
    benchmark_outperformance_ratio: float


def generate_walk_forward_folds(
    dataset: HistoricalDataset, configuration: WalkForwardConfiguration
) -> tuple[WalkForwardFold, ...]:
    bars = dataset.bars
    folds: list[WalkForwardFold] = []
    offset = 0
    while True:
        training_start = (
            0 if configuration.mode is WalkForwardMode.EXPANDING else offset
        )
        test_start = offset + configuration.training_window
        test_end_exclusive = test_start + configuration.test_window
        if test_end_exclusive > len(bars):
            break
        folds.append(
            WalkForwardFold(
                index=len(folds) + 1,
                training_start=bars[training_start].timestamp,
                training_end=bars[test_start - 1].timestamp,
                test_start=bars[test_start].timestamp,
                test_end=bars[test_end_exclusive - 1].timestamp,
                warmup_start=bars[training_start].timestamp,
                training_start_index=training_start,
                test_start_index=test_start,
                test_end_index=test_end_exclusive - 1,
            )
        )
        offset += configuration.step
    if not folds:
        raise ValueError("walk-forward configuration produces zero complete folds")
    return tuple(folds)


def aggregate_walk_forward(
    fold_results: tuple[WalkForwardFoldResult, ...],
) -> WalkForwardAggregate:
    if not fold_results:
        raise ValueError("at least one fold result is required")
    returns = [_required(item.strategy_metrics.total_return) for item in fold_results]
    sharpes = [
        value
        for item in fold_results
        if (value := item.strategy_metrics.sharpe) is not None
    ]
    drawdowns = [
        value
        for item in fold_results
        if (value := item.strategy_metrics.max_drawdown) is not None
    ]
    trade_counts = [
        value
        for item in fold_results
        if (value := item.strategy_metrics.trade_count) is not None
    ]
    profitable = sum(value > 0 for value in returns)
    outperformance = sum(item.excess_total_return > 0 for item in fold_results)
    count = len(fold_results)
    return WalkForwardAggregate(
        fold_count=count,
        profitable_fold_count=profitable,
        profitable_fold_ratio=profitable / count,
        mean_total_return=fmean(returns),
        median_total_return=median(returns),
        return_std_across_folds=pstdev(returns),
        mean_sharpe=fmean(sharpes) if sharpes else None,
        median_sharpe=median(sharpes) if sharpes else None,
        sharpe_std_across_folds=pstdev(sharpes) if sharpes else None,
        worst_max_drawdown=min(drawdowns) if drawdowns else None,
        median_trade_count=median(trade_counts) if trade_counts else None,
        benchmark_outperformance_count=outperformance,
        benchmark_outperformance_ratio=outperformance / count,
    )


def _required(value: float | None) -> float:
    if value is None:
        raise ValueError("fold total return is required")
    return value
