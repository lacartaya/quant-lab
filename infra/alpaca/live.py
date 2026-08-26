from datetime import datetime

from infra.alpaca.historical import _parse_bar
from infra.alpaca.http import AlpacaHTTPClient
from quant.domain import MarketBar


class AlpacaLiveMarketDataProvider:
    """Polling adapter for the latest free-tier IEX equity bar."""

    name = "alpaca_iex"
    version = "alpaca-iex-polling-v1"

    def __init__(
        self, client: AlpacaHTTPClient, symbol: str, after: datetime | None = None
    ) -> None:
        self._client = client
        self._symbol = symbol.upper()
        self._after = after

    def next_bar(self) -> MarketBar | None:
        payload = self._client.market_data_get(
            f"/v2/stocks/{self._symbol}/bars/latest", {"feed": "iex"}
        )
        raw = payload.get("bar")
        if raw is None:
            return None
        bar = _parse_bar(raw)
        if self._after is not None and bar.timestamp <= self._after:
            return None
        self._after = bar.timestamp
        return bar
