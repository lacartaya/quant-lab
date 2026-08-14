from collections.abc import Sequence
from typing import Protocol

from quant.domain import HistoricalDataset, Signal


class ExecutableStrategy(Protocol):
    """Contract for deterministic signal-generating strategy behavior."""

    @property
    def strategy_key(self) -> str: ...

    def generate_signals(self, dataset: HistoricalDataset) -> Sequence[Signal]: ...
