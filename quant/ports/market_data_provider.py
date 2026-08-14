from typing import Protocol

from quant.domain import HistoricalDataRequest, HistoricalDataset


class MarketDataProvider(Protocol):
    @property
    def name(self) -> str: ...

    def load_historical(self, request: HistoricalDataRequest) -> HistoricalDataset: ...
