from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from infra.market_data import CsvMarketDataProvider, MarketDataFormatError
from quant.application import canonical_bars_checksum
from quant.domain import AdjustmentPolicy, HistoricalDataRequest

FIXTURE = Path("tests/fixtures/market_data/sample_ohlcv.csv")


def request() -> HistoricalDataRequest:
    return HistoricalDataRequest(
        "US equities",
        "ABC",
        "daily",
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 4, tzinfo=UTC),
        AdjustmentPolicy.RAW,
    )


def test_csv_provider_normalizes_and_sorts_rows() -> None:
    dataset = CsvMarketDataProvider(FIXTURE).load_historical(request())
    assert len(dataset.bars) == 2
    assert dataset.bars[0].timestamp == datetime(2024, 1, 2, tzinfo=UTC)
    assert dataset.bars[0].open == Decimal("472.16")
    assert dataset.bars[1].volume == Decimal("234567")


def test_equivalent_csv_order_and_format_have_same_checksum(tmp_path: Path) -> None:
    reordered = tmp_path / "reordered.csv"
    reordered.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2024-01-02T01:00:00+01:00,472.160,473.670,470.490,472.650,123456.0\n"
        "2024-01-03T00:00:00Z,470.430,471.190,468.170,468.790,234567.00\n",
        encoding="utf-8",
    )
    original = CsvMarketDataProvider(FIXTURE).load_historical(request())
    equivalent = CsvMarketDataProvider(reordered).load_historical(request())
    assert original.bars == equivalent.bars
    assert canonical_bars_checksum(original.bars) == canonical_bars_checksum(
        equivalent.bars
    )


def test_csv_provider_rejects_invalid_data(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.csv"
    invalid.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2024-01-02T00:00:00Z,10,9,8,10,-1\n",
        encoding="utf-8",
    )
    with pytest.raises(MarketDataFormatError, match="invalid market data"):
        CsvMarketDataProvider(invalid).load_historical(request())


def test_csv_provider_filters_to_requested_range() -> None:
    narrow_request = HistoricalDataRequest(
        "US equities",
        "ABC",
        "daily",
        datetime(2024, 1, 3, tzinfo=UTC),
        datetime(2024, 1, 4, tzinfo=UTC),
        AdjustmentPolicy.RAW,
    )
    dataset = CsvMarketDataProvider(FIXTURE).load_historical(narrow_request)
    assert [bar.timestamp for bar in dataset.bars] == [
        datetime(2024, 1, 3, tzinfo=UTC)
    ]
