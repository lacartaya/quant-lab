from dataclasses import dataclass
from datetime import datetime
from decimal import Context, Decimal, localcontext
from typing import ClassVar

from quant.domain import HistoricalDataset, Signal, SignalAction


@dataclass(frozen=True, slots=True)
class MovingAveragePoint:
    timestamp: datetime
    short_average: Decimal
    long_average: Decimal


@dataclass(frozen=True, slots=True)
class MovingAverageParameters:
    short_window: int
    long_window: int

    def __post_init__(self) -> None:
        short_is_integer = isinstance(self.short_window, int) and not isinstance(
            self.short_window, bool
        )
        if not short_is_integer:
            raise TypeError("short_window must be an integer")
        if not isinstance(self.long_window, int) or isinstance(self.long_window, bool):
            raise TypeError("long_window must be an integer")
        if self.short_window <= 0:
            raise ValueError("short_window must be positive")
        if self.long_window <= 0:
            raise ValueError("long_window must be positive")
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be less than long_window")

    def as_dict(self) -> dict[str, int]:
        return {
            "short_window": self.short_window,
            "long_window": self.long_window,
        }


BASELINE_MOVING_AVERAGE_PARAMETERS = MovingAverageParameters(
    short_window=50,
    long_window=200,
)


@dataclass(frozen=True, slots=True)
class MovingAverageTrendStrategy:
    parameters: MovingAverageParameters = BASELINE_MOVING_AVERAGE_PARAMETERS

    strategy_key: ClassVar[str] = "moving_average_trend"

    def indicator_series(
        self, dataset: HistoricalDataset
    ) -> tuple[MovingAveragePoint, ...]:
        closes = tuple(bar.close for bar in dataset.bars)
        if len(closes) < self.parameters.long_window:
            return ()

        points: list[MovingAveragePoint] = []
        with localcontext(Context(prec=64)):
            prefix_sums: list[Decimal] = [Decimal(0)]
            for close in closes:
                prefix_sums.append(prefix_sums[-1] + close)

            for index in range(self.parameters.long_window - 1, len(closes)):
                count = index + 1
                short_sum = (
                    prefix_sums[count]
                    - prefix_sums[count - self.parameters.short_window]
                )
                long_sum = (
                    prefix_sums[count]
                    - prefix_sums[count - self.parameters.long_window]
                )
                short_average = short_sum / Decimal(self.parameters.short_window)
                long_average = long_sum / Decimal(self.parameters.long_window)
                points.append(
                    MovingAveragePoint(
                        dataset.bars[index].timestamp, short_average, long_average
                    )
                )
        return tuple(points)

    def generate_signals(self, dataset: HistoricalDataset) -> tuple[Signal, ...]:
        return tuple(
            Signal(
                point.timestamp,
                SignalAction.LONG
                if point.short_average > point.long_average
                else SignalAction.FLAT,
            )
            for point in self.indicator_series(dataset)
        )
