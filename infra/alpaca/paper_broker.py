from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

from infra.alpaca.http import AlpacaAPIError, AlpacaHTTPClient
from quant.domain.paper_broker import (
    AlpacaPaperAccount,
    AlpacaPaperFill,
    AlpacaPaperOrder,
    AlpacaPaperPosition,
    SubmitAlpacaPaperOrder,
)


class AlpacaPaperBrokerAdapter:
    def __init__(
        self,
        client: AlpacaHTTPClient,
        order_sink: Callable[[AlpacaPaperOrder], None] | None = None,
    ) -> None:
        self._client = client
        self._order_sink = order_sink

    def _track(self, order: AlpacaPaperOrder) -> AlpacaPaperOrder:
        if self._order_sink is not None:
            self._order_sink(order)
        return order

    def get_account(self) -> AlpacaPaperAccount:
        value = _object(self._client.paper_get("/v2/account"), "account")
        return AlpacaPaperAccount(
            _text(value, "id"),
            _text(value, "account_number"),
            _text(value, "status"),
            _text(value, "currency"),
            _decimal(value, "cash"),
            _decimal(value, "buying_power"),
            _decimal(value, "equity"),
            _decimal(value, "portfolio_value"),
            bool(value.get("trading_blocked", False)),
            bool(value.get("pattern_day_trader", False)),
        )

    def submit_order(self, request: SubmitAlpacaPaperOrder) -> AlpacaPaperOrder:
        value = self._client.paper_post(
            "/v2/orders",
            {
                "symbol": request.symbol.upper(),
                "qty": str(request.quantity),
                "side": request.side.value,
                "type": request.order_type.value,
                "time_in_force": request.time_in_force.value,
                "client_order_id": request.client_order_id,
            },
        )
        return self._track(_order(_object(value, "order")))

    def list_orders(self, status: str = "open") -> tuple[AlpacaPaperOrder, ...]:
        if status not in {"open", "closed", "all"}:
            raise ValueError("order status filter must be open, closed, or all")
        values = _array(
            self._client.paper_get(
                "/v2/orders", {"status": status, "limit": 100, "direction": "desc"}
            ),
            "orders",
        )
        return tuple(self._track(_order(_object(value, "order"))) for value in values)

    def get_order(self, order_id: str) -> AlpacaPaperOrder:
        return self._track(
            _order(
                _object(
                    self._client.paper_get(f"/v2/orders/{quote(order_id, safe='')}"),
                    "order",
                )
            )
        )

    def list_positions(self) -> tuple[AlpacaPaperPosition, ...]:
        values = _array(self._client.paper_get("/v2/positions"), "positions")
        return tuple(_position(_object(value, "position")) for value in values)

    def get_position(self, symbol: str) -> AlpacaPaperPosition:
        return _position(
            _object(
                self._client.paper_get(
                    f"/v2/positions/{quote(symbol.upper(), safe='')}"
                ),
                "position",
            )
        )

    def close_position(self, symbol: str) -> AlpacaPaperOrder:
        return self._track(
            _order(
                _object(
                    self._client.paper_delete(
                        f"/v2/positions/{quote(symbol.upper(), safe='')}"
                    ),
                    "close order",
                )
            )
        )

    def list_fills(self) -> tuple[AlpacaPaperFill, ...]:
        values = _array(
            self._client.paper_get(
                "/v2/account/activities/FILL", {"direction": "desc", "page_size": 100}
            ),
            "fills",
        )
        return tuple(_fill(_object(value, "fill")) for value in values)


def _order(value: dict[str, Any]) -> AlpacaPaperOrder:
    return AlpacaPaperOrder(
        _text(value, "id"),
        _text(value, "client_order_id"),
        _text(value, "symbol"),
        _text(value, "side"),
        _text(value, "type"),
        _text(value, "time_in_force"),
        _text(value, "status"),
        _decimal(value, "qty"),
        _decimal(value, "filled_qty"),
        _optional_decimal(value, "filled_avg_price"),
        _optional_datetime(value, "submitted_at"),
        _optional_datetime(value, "filled_at"),
    )


def _position(value: dict[str, Any]) -> AlpacaPaperPosition:
    return AlpacaPaperPosition(
        _text(value, "symbol"),
        _decimal(value, "qty"),
        _decimal(value, "avg_entry_price"),
        _decimal(value, "market_value"),
        _decimal(value, "current_price"),
        _decimal(value, "unrealized_pl"),
        _decimal(value, "unrealized_plpc"),
    )


def _fill(value: dict[str, Any]) -> AlpacaPaperFill:
    timestamp = _optional_datetime(value, "transaction_time")
    if timestamp is None:
        raise AlpacaAPIError(502, "Alpaca fill is missing transaction_time")
    return AlpacaPaperFill(
        _text(value, "id"),
        _text(value, "order_id"),
        _text(value, "symbol"),
        _text(value, "side"),
        _decimal(value, "qty"),
        _decimal(value, "price"),
        timestamp,
        _text(value, "activity_type"),
    )


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AlpacaAPIError(502, f"Alpaca {label} response is invalid")
    return value


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise AlpacaAPIError(502, f"Alpaca {label} response is invalid")
    return value


def _text(value: dict[str, Any], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw:
        raise AlpacaAPIError(502, f"Alpaca response is missing {key}")
    return raw


def _decimal(value: dict[str, Any], key: str) -> Decimal:
    raw = value.get(key)
    try:
        return Decimal(str(raw))
    except InvalidOperation as error:
        raise AlpacaAPIError(502, f"Alpaca response has invalid {key}") from error


def _optional_decimal(value: dict[str, Any], key: str) -> Decimal | None:
    return None if value.get(key) is None else _decimal(value, key)


def _optional_datetime(value: dict[str, Any], key: str) -> datetime | None:
    raw = value.get(key)
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError as error:
        raise AlpacaAPIError(502, f"Alpaca response has invalid {key}") from error
