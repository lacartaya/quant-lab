from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from infra.alpaca.http import AlpacaAPIError, AlpacaHTTPClient
from quant.domain import HistoricalDataRequest, HistoricalDataset, MarketBar


class AlpacaHistoricalMarketDataProvider:
    # DatasetSnapshot deliberately remains vendor-neutral. The immutable provider
    # identity carries the selected feed so the material provenance is retained.
    def __init__(self, client: AlpacaHTTPClient, feed: str = "iex") -> None:
        normalized_feed = feed.lower()
        if normalized_feed not in {"iex", "sip"}:
            raise ValueError("Alpaca historical feed must be IEX or SIP")
        self._client = client
        self.feed = normalized_feed

    @property
    def name(self) -> str:
        return f"alpaca:{self.feed}"

    def load_historical(self, request: HistoricalDataRequest) -> HistoricalDataset:
        if request.market != "US_EQUITIES":
            raise ValueError("Alpaca historical import supports US_EQUITIES only")
        timeframe_map = {"1Day": "1Day", "1D": "1Day", "1Min": "1Min"}
        if request.timeframe not in timeframe_map:
            raise ValueError(
                "Alpaca historical import supports 1Day and 1Min bars only"
            )
        alpaca_timeframe = timeframe_map[request.timeframe]
        bars: list[MarketBar] = []
        page_token: str | None = None
        while True:
            params: dict[str, object] = {
                "symbols": request.instrument.upper(),
                "timeframe": alpaca_timeframe,
                "start": request.start_at.isoformat(),
                "end": request.end_at.isoformat(),
                "limit": 10000,
                "feed": self.feed,
                "adjustment": (
                    "raw" if request.adjustment_policy.value == "raw" else "all"
                ),
                "sort": "asc",
            }
            if page_token is not None:
                params["page_token"] = page_token
            payload = self._client.market_data_get("/v2/stocks/bars", params)
            bars.extend(_parse_bars(payload, request.instrument.upper()))
            raw_token = payload.get("next_page_token")
            page_token = raw_token if isinstance(raw_token, str) and raw_token else None
            if page_token is None:
                break
        if not bars:
            raise AlpacaAPIError(404, "Alpaca returned no bars for the requested range")
        return HistoricalDataset.from_bars(
            market=request.market,
            instrument=request.instrument.upper(),
            timeframe=request.timeframe,
            adjustment_policy=request.adjustment_policy,
            bars=bars,
            metadata={
                "provider": self.name,
                "feed": self.feed,
                "requested_start": request.start_at.isoformat(),
                "requested_end": request.end_at.isoformat(),
                "actual_start": bars[0].timestamp.isoformat(),
                "actual_end": bars[-1].timestamp.isoformat(),
            },
        )


def _parse_bars(payload: Mapping[str, Any], symbol: str) -> list[MarketBar]:
    collection = payload.get("bars")
    if not isinstance(collection, dict):
        raise AlpacaAPIError(502, "Alpaca bars response is missing bars")
    values = collection.get(symbol)
    if values is None:
        return []
    if not isinstance(values, list):
        raise AlpacaAPIError(502, "Alpaca symbol bars are invalid")
    return [_parse_bar(value) for value in values]


def _parse_bar(value: object) -> MarketBar:
    if not isinstance(value, dict):
        raise AlpacaAPIError(502, "Alpaca bar is invalid")
    try:
        return MarketBar(
            datetime.fromisoformat(str(value["t"]).replace("Z", "+00:00")),
            Decimal(str(value["o"])),
            Decimal(str(value["h"])),
            Decimal(str(value["l"])),
            Decimal(str(value["c"])),
            Decimal(str(value["v"])),
        )
    except (KeyError, ValueError, InvalidOperation) as error:
        raise AlpacaAPIError(502, "Alpaca bar cannot be normalized") from error
