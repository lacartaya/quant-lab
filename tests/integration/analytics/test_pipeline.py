from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant.analytics import (
    AnalyticsConfiguration,
    analyze_backtest,
    buy_and_hold_benchmark,
    compare_to_benchmark,
)
from quant.backtest import (
    BacktestConfiguration,
    BacktestEngine,
    BasisPointsSlippageModel,
    PercentageFeeModel,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import AdjustmentPolicy, HistoricalDataset, MarketBar
from quant.strategies import MovingAverageParameters, MovingAverageTrendStrategy


def dataset() -> HistoricalDataset:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    closes = ["3", "2", "1", "4", "5", "8", "1", "7"]
    return HistoricalDataset.from_bars(
        market="Test",
        instrument="TEST",
        timeframe="daily",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=(
            MarketBar(
                start + timedelta(days=index),
                Decimal(close),
                Decimal(close),
                Decimal(close),
                Decimal(close),
                Decimal("100"),
            )
            for index, close in enumerate(closes)
        ),
    )


def test_full_strategy_analytics_and_benchmark_pipeline() -> None:
    data = dataset()
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))
    free_configuration = BacktestConfiguration(
        Decimal("100"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
    )
    costly_configuration = BacktestConfiguration(
        Decimal("100"),
        Decimal("1"),
        PercentageFeeModel(Decimal("0.01")),
        BasisPointsSlippageModel(Decimal("10")),
    )
    analytics_configuration = AnalyticsConfiguration(252)
    engine = BacktestEngine()

    free_metrics = analyze_backtest(
        engine.run(data, strategy, free_configuration), analytics_configuration
    )
    costly_metrics = analyze_backtest(
        engine.run(data, strategy, costly_configuration), analytics_configuration
    )
    benchmark = buy_and_hold_benchmark(
        data, free_configuration, analytics_configuration
    )
    comparison = compare_to_benchmark(free_metrics, benchmark.metrics)

    assert costly_metrics.total_return is not None
    assert free_metrics.total_return is not None
    assert costly_metrics.total_return < free_metrics.total_return
    assert comparison.strategy_metrics == free_metrics
    assert comparison.benchmark_metrics == benchmark.metrics
    assert (
        engine.run(data, strategy, free_configuration)
        == engine.run(data, strategy, free_configuration)
    )
