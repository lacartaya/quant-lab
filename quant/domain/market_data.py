from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from quant.domain._validation import (
    as_utc,
    immutable_mapping,
    require_enum,
    require_text,
)
from quant.domain.dataset import AdjustmentPolicy


@dataclass(frozen=True, slots=True)
class MarketBar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        timestamp = as_utc(self.timestamp, "timestamp")
        values = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
        for field_name, value in values.items():
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError(f"{field_name} must be a finite Decimal")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")
        if self.high < max(self.open, self.low, self.close):
            raise ValueError(
                "high must be greater than or equal to open, low, and close"
            )
        if self.low > min(self.open, self.high, self.close):
            raise ValueError("low must be less than or equal to open, high, and close")
        object.__setattr__(self, "timestamp", timestamp)


@dataclass(frozen=True, slots=True)
class HistoricalDataRequest:
    market: str
    instrument: str
    timeframe: str
    start_at: datetime
    end_at: datetime
    adjustment_policy: AdjustmentPolicy

    def __post_init__(self) -> None:
        require_text(self.market, "market")
        require_text(self.instrument, "instrument")
        require_text(self.timeframe, "timeframe")
        require_enum(self.adjustment_policy, AdjustmentPolicy, "adjustment_policy")
        start_at = as_utc(self.start_at, "start_at")
        end_at = as_utc(self.end_at, "end_at")
        if end_at <= start_at:
            raise ValueError("end_at must be after start_at")
        object.__setattr__(self, "start_at", start_at)
        object.__setattr__(self, "end_at", end_at)


@dataclass(frozen=True, slots=True)
class HistoricalDataset:
    market: str
    instrument: str
    timeframe: str
    adjustment_policy: AdjustmentPolicy
    bars: tuple[MarketBar, ...]
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        require_text(self.market, "market")
        require_text(self.instrument, "instrument")
        require_text(self.timeframe, "timeframe")
        require_enum(self.adjustment_policy, AdjustmentPolicy, "adjustment_policy")
        if not self.bars:
            raise ValueError("historical dataset must contain at least one bar")
        ordered = tuple(sorted(self.bars, key=lambda bar: bar.timestamp))
        timestamps = [bar.timestamp for bar in ordered]
        if len(timestamps) != len(set(timestamps)):
            raise ValueError("historical dataset contains duplicate timestamps")
        object.__setattr__(self, "bars", ordered)
        object.__setattr__(self, "metadata", immutable_mapping(self.metadata))

    @classmethod
    def from_bars(
        cls,
        *,
        market: str,
        instrument: str,
        timeframe: str,
        adjustment_policy: AdjustmentPolicy,
        bars: Iterable[MarketBar],
        metadata: Mapping[str, object] | None = None,
    ) -> "HistoricalDataset":
        return cls(
            market=market,
            instrument=instrument,
            timeframe=timeframe,
            adjustment_policy=adjustment_policy,
            bars=tuple(bars),
            metadata={} if metadata is None else metadata,
        )

    def validate_range(self, start_at: datetime, end_at: datetime) -> None:
        normalized_start = as_utc(start_at, "start_at")
        normalized_end = as_utc(end_at, "end_at")
        if any(
            bar.timestamp < normalized_start or bar.timestamp > normalized_end
            for bar in self.bars
        ):
            raise ValueError("historical dataset contains bars outside requested range")
