"""Deterministic executable strategy implementations."""

from quant.strategies.base import ExecutableStrategy
from quant.strategies.moving_average_trend import (
    BASELINE_MOVING_AVERAGE_PARAMETERS,
    MovingAverageParameters,
    MovingAverageTrendStrategy,
)

__all__ = [
    "BASELINE_MOVING_AVERAGE_PARAMETERS",
    "ExecutableStrategy",
    "MovingAverageParameters",
    "MovingAverageTrendStrategy",
]
