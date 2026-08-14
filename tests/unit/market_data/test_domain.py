from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from quant.domain import (
    AdjustmentPolicy,
    HistoricalDataRequest,
    HistoricalDataset,
    MarketBar,
)

NOW = datetime(2024, 1, 2, tzinfo=UTC)


def make_bar(
    *,
    timestamp: datetime = NOW,
    open_price: str = "10",
    high: str = "12",
    low: str = "9",
    close: str = "11",
    volume: str = "100",
) -> MarketBar:
    return MarketBar(
        timestamp,
        Decimal(open_price),
        Decimal(high),
        Decimal(low),
        Decimal(close),
        Decimal(volume),
    )


def test_valid_bar_uses_decimal_and_normalizes_timestamp_to_utc() -> None:
    timestamp = datetime(2024, 1, 2, 1, tzinfo=timezone(timedelta(hours=1)))
    bar = make_bar(timestamp=timestamp)
    assert bar.timestamp == NOW
    assert bar.close == Decimal("11")


@pytest.mark.parametrize(
    ("open_price", "high", "low", "close"),
    [
        ("13", "12", "9", "11"),
        ("10", "12", "9", "13"),
        ("10", "8", "9", "11"),
        ("8", "12", "9", "11"),
        ("10", "12", "9", "8"),
        ("10", "8", "9", "8.5"),
    ],
)
def test_invalid_ohlc_relationships_are_rejected(
    open_price: str, high: str, low: str, close: str
) -> None:
    with pytest.raises(ValueError):
        make_bar(open_price=open_price, high=high, low=low, close=close)


def test_negative_volume_is_rejected() -> None:
    with pytest.raises(ValueError, match="volume cannot be negative"):
        make_bar(volume="-1")


def test_dataset_sorts_bars_chronologically() -> None:
    later = make_bar(timestamp=NOW + timedelta(days=1))
    earlier = make_bar()
    dataset = HistoricalDataset.from_bars(
        market="US equities",
        instrument="ABC",
        timeframe="daily",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=[later, earlier],
    )
    assert dataset.bars == (earlier, later)


def test_dataset_rejects_duplicate_timestamps() -> None:
    with pytest.raises(ValueError, match="duplicate timestamps"):
        HistoricalDataset.from_bars(
            market="US equities",
            instrument="ABC",
            timeframe="daily",
            adjustment_policy=AdjustmentPolicy.RAW,
            bars=[make_bar(), make_bar(close="10.5")],
        )


def test_requested_range_is_enforced() -> None:
    dataset = HistoricalDataset.from_bars(
        market="US equities",
        instrument="ABC",
        timeframe="daily",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=[make_bar()],
    )
    with pytest.raises(ValueError, match="outside requested range"):
        dataset.validate_range(NOW + timedelta(seconds=1), NOW + timedelta(days=1))


def test_request_requires_ordered_timezone_aware_range() -> None:
    with pytest.raises(ValueError, match="end_at must be after start_at"):
        HistoricalDataRequest(
            "US equities",
            "ABC",
            "daily",
            NOW,
            NOW,
            AdjustmentPolicy.RAW,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        HistoricalDataRequest(
            "US equities",
            "ABC",
            "daily",
            datetime(2024, 1, 1),
            NOW,
            AdjustmentPolicy.RAW,
        )
