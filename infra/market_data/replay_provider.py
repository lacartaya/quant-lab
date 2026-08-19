from dataclasses import dataclass, field
from datetime import datetime

from quant.domain import HistoricalDataset, MarketBar


@dataclass(slots=True)
class ReplayMarketDataProvider:
    dataset: HistoricalDataset
    after: datetime | None = None
    name: str = "replay"
    version: str = "replay-provider-v1"
    _eligible: tuple[MarketBar, ...] = field(init=False, repr=False)
    _index: int = field(init=False, default=0, repr=False)
    _emitted: list[MarketBar] = field(init=False, default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._eligible = tuple(
            bar
            for bar in self.dataset.bars
            if self.after is None or bar.timestamp > self.after
        )

    def next_bar(self) -> MarketBar | None:
        if self._index == len(self._eligible):
            return None
        bar = self._eligible[self._index]
        self._index += 1
        self._emitted.append(bar)
        return bar

    @property
    def emitted(self) -> tuple[MarketBar, ...]:
        return tuple(self._emitted)
