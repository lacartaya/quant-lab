from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant.backtest import (
    BacktestConfiguration,
    BacktestEngine,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import AdjustmentPolicy, HistoricalDataset, MarketBar
from quant.strategies import MovingAverageParameters, MovingAverageTrendStrategy


def test_market_data_strategy_backtest_pipeline() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    closes = ["3", "2", "1", "4", "5", "2", "1"]
    bars = tuple(
        MarketBar(
            start + timedelta(days=index),
            Decimal(close),
            Decimal(close),
            Decimal(close),
            Decimal(close),
            Decimal("100"),
        )
        for index, close in enumerate(closes)
    )
    dataset = HistoricalDataset.from_bars(
        market="Test market",
        instrument="TEST",
        timeframe="daily",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=bars,
    )
    result = BacktestEngine().run(
        dataset,
        MovingAverageTrendStrategy(MovingAverageParameters(2, 3)),
        BacktestConfiguration(
            Decimal("100"),
            Decimal("1"),
            ZeroFeeModel(),
            ZeroSlippageModel(),
        ),
    )
    assert len(result.orders) == 2
    assert result.orders[0].timestamp == start + timedelta(days=4)
    assert result.orders[1].timestamp == start + timedelta(days=6)
    assert result.orders[0].reference_price == bars[4].open
    assert result.open_position is None
