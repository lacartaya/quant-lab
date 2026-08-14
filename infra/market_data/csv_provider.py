import csv
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from quant.domain import HistoricalDataRequest, HistoricalDataset, MarketBar


class MarketDataFormatError(ValueError):
    """Raised when provider data cannot be normalized safely."""


class CsvMarketDataProvider:
    name = "csv"
    _fields = ("timestamp", "open", "high", "low", "close", "volume")

    def __init__(
        self,
        source: Path,
        column_mapping: Mapping[str, str] | None = None,
    ) -> None:
        self._source = source
        self._columns = dict(column_mapping or {field: field for field in self._fields})
        missing = set(self._fields) - self._columns.keys()
        if missing:
            raise ValueError(f"column mapping is missing fields: {sorted(missing)}")

    def load_historical(self, request: HistoricalDataRequest) -> HistoricalDataset:
        try:
            with self._source.open(encoding="utf-8", newline="") as source_file:
                reader = csv.DictReader(source_file)
                self._validate_headers(reader.fieldnames)
                bars = [
                    bar
                    for line_number, row in enumerate(reader, start=2)
                    if request.start_at
                    <= (bar := self._parse_row(row, line_number)).timestamp
                    <= request.end_at
                ]
        except OSError as error:
            raise MarketDataFormatError(
                f"cannot read CSV source: {self._source}"
            ) from error

        return HistoricalDataset.from_bars(
            market=request.market,
            instrument=request.instrument,
            timeframe=request.timeframe,
            adjustment_policy=request.adjustment_policy,
            bars=bars,
            metadata={"source": self._source.name},
        )

    def _validate_headers(self, headers: Sequence[str] | None) -> None:
        available = set(headers or [])
        missing = set(self._columns.values()) - available
        if missing:
            raise MarketDataFormatError(f"CSV is missing columns: {sorted(missing)}")

    def _parse_row(self, row: Mapping[str, str | None], line_number: int) -> MarketBar:
        try:
            timestamp_text = self._required_value(row, "timestamp")
            timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
            return MarketBar(
                timestamp=timestamp,
                open=Decimal(self._required_value(row, "open")),
                high=Decimal(self._required_value(row, "high")),
                low=Decimal(self._required_value(row, "low")),
                close=Decimal(self._required_value(row, "close")),
                volume=Decimal(self._required_value(row, "volume")),
            )
        except (InvalidOperation, ValueError) as error:
            raise MarketDataFormatError(
                f"invalid market data at CSV line {line_number}: {error}"
            ) from error

    def _required_value(self, row: Mapping[str, str | None], field: str) -> str:
        value = row.get(self._columns[field])
        if value is None or not value.strip():
            raise ValueError(f"{field} is required")
        return value.strip()
