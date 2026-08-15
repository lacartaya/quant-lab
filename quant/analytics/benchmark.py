from dataclasses import dataclass

from quant.analytics.configuration import AnalyticsConfiguration
from quant.analytics.service import METRICS_VERSION, analyze_backtest
from quant.backtest import (
    BacktestConfiguration,
    BacktestResult,
    ExecutionSimulator,
    Order,
    OrderSide,
    Portfolio,
    maximum_affordable_quantity,
)
from quant.domain import HistoricalDataset, MetricSet


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    backtest_result: BacktestResult
    metrics: MetricSet
    metrics_version: str = METRICS_VERSION


@dataclass(frozen=True, slots=True)
class PerformanceComparison:
    strategy_metrics: MetricSet
    benchmark_metrics: MetricSet
    excess_total_return: float
    metrics_version: str = METRICS_VERSION


def buy_and_hold_benchmark(
    dataset: HistoricalDataset,
    backtest_configuration: BacktestConfiguration,
    analytics_configuration: AnalyticsConfiguration,
) -> BenchmarkResult:
    first_bar = dataset.bars[0]
    quantity = maximum_affordable_quantity(
        cash=backtest_configuration.initial_cash,
        fraction=backtest_configuration.position_fraction,
        reference_price=first_bar.open,
        fee_model=backtest_configuration.fee_model,
        slippage_model=backtest_configuration.slippage_model,
    )
    portfolio = Portfolio(backtest_configuration.initial_cash)
    orders = []
    fills = []
    if quantity > 0:
        order = Order(
            "BENCHMARK-ORDER-000001",
            first_bar.timestamp,
            OrderSide.BUY,
            quantity,
            first_bar.open,
        )
        fill = ExecutionSimulator(
            backtest_configuration.fee_model,
            backtest_configuration.slippage_model,
        ).execute(order)
        portfolio.apply_buy(fill)
        orders.append(order)
        fills.append(fill)
    equity_curve = tuple(
        portfolio.mark(bar.timestamp, bar.close) for bar in dataset.bars
    )
    final_point = equity_curve[-1]
    result = BacktestResult(
        configuration=backtest_configuration,
        initial_cash=backtest_configuration.initial_cash,
        final_cash=portfolio.cash,
        final_equity=final_point.equity,
        signals=(),
        orders=tuple(orders),
        fills=tuple(fills),
        trades=(),
        equity_curve=equity_curve,
        open_position=portfolio.position(dataset.bars[-1].close),
        skipped_signals=(),
        unexecuted_signals=(),
    )
    return BenchmarkResult(
        name="BUY_AND_HOLD",
        backtest_result=result,
        metrics=analyze_backtest(result, analytics_configuration),
    )


def compare_to_benchmark(
    strategy_metrics: MetricSet, benchmark_metrics: MetricSet
) -> PerformanceComparison:
    if (
        strategy_metrics.total_return is None
        or benchmark_metrics.total_return is None
    ):
        raise ValueError("total return is required for benchmark comparison")
    return PerformanceComparison(
        strategy_metrics=strategy_metrics,
        benchmark_metrics=benchmark_metrics,
        excess_total_return=(
            strategy_metrics.total_return - benchmark_metrics.total_return
        ),
    )
