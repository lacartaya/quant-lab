from typing import Protocol

from quant.domain import MarketBar


class LiveMarketDataProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def next_bar(self) -> MarketBar | None: ...
