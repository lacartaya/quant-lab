from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.analytics import (
    AnalyticsConfiguration,
    buy_and_hold_benchmark,
    compare_to_benchmark,
)
from quant.backtest import (
    BacktestConfiguration,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import AdjustmentPolicy, HistoricalDataset, MarketBar, MetricSet


def dataset() -> HistoricalDataset:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    bars = tuple(
        MarketBar(
            start + timedelta(days=index),
            Decimal(open_price),
            max(Decimal(open_price), Decimal(close)),
            min(Decimal(open_price), Decimal(close)),
            Decimal(close),
            Decimal("100"),
        )
        for index, (open_price, close) in enumerate(
            [("10", "11"), ("12", "13"), ("14", "15")]
        )
    )
    return HistoricalDataset.from_bars(
        market="Test",
        instrument="TEST",
        timeframe="daily",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=bars,
    )


def test_buy_and_hold_buys_first_open_and_marks_final_close() -> None:
    benchmark = buy_and_hold_benchmark(
        dataset(),
        BacktestConfiguration(
            Decimal("100"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
        ),
        AnalyticsConfiguration(252),
    )
    assert benchmark.name == "BUY_AND_HOLD"
    assert benchmark.backtest_result.orders[0].reference_price == Decimal("10")
    assert benchmark.backtest_result.orders[0].quantity == 10
    assert benchmark.backtest_result.final_equity == Decimal("150")
    assert benchmark.metrics.total_return == 0.5


def test_comparison_reports_difference_without_ranking() -> None:
    comparison = compare_to_benchmark(
        MetricSet(total_return=0.1), MetricSet(total_return=0.15)
    )
    assert comparison.excess_total_return == pytest.approx(-0.05)
