from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from quant.domain._validation import as_utc, require_enum, require_text


def _positive_decimal(value: Decimal, field_name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ValueError(f"{field_name} must be a positive finite Decimal")


def _non_negative_decimal(value: Decimal, field_name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{field_name} must be a non-negative finite Decimal")


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    timestamp: datetime
    side: OrderSide
    quantity: int
    reference_price: Decimal

    def __post_init__(self) -> None:
        require_text(self.id, "id")
        require_enum(self.side, OrderSide, "side")
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool):
            raise TypeError("quantity must be an integer")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        _positive_decimal(self.reference_price, "reference_price")
        object.__setattr__(self, "timestamp", as_utc(self.timestamp, "timestamp"))


@dataclass(frozen=True, slots=True)
class Fill:
    order_id: str
    timestamp: datetime
    side: OrderSide
    quantity: int
    reference_price: Decimal
    fill_price: Decimal
    fees: Decimal
    slippage: Decimal

    def __post_init__(self) -> None:
        require_text(self.order_id, "order_id")
        require_enum(self.side, OrderSide, "side")
        if (
            not isinstance(self.quantity, int)
            or isinstance(self.quantity, bool)
            or self.quantity <= 0
        ):
            raise ValueError("quantity must be a positive integer")
        _positive_decimal(self.reference_price, "reference_price")
        _positive_decimal(self.fill_price, "fill_price")
        _non_negative_decimal(self.fees, "fees")
        _non_negative_decimal(self.slippage, "slippage")
        object.__setattr__(self, "timestamp", as_utc(self.timestamp, "timestamp"))


@dataclass(frozen=True, slots=True)
class Position:
    quantity: int
    average_entry_price: Decimal
    entry_fees: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("position quantity must be positive")
        _positive_decimal(self.average_entry_price, "average_entry_price")
        _non_negative_decimal(self.entry_fees, "entry_fees")
        _non_negative_decimal(self.market_value, "market_value")


@dataclass(frozen=True, slots=True)
class Trade:
    entry_timestamp: datetime
    entry_price: Decimal
    exit_timestamp: datetime
    exit_price: Decimal
    quantity: int
    entry_fees: Decimal
    exit_fees: Decimal
    realized_pnl: Decimal

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("trade quantity must be positive")
        _positive_decimal(self.entry_price, "entry_price")
        _positive_decimal(self.exit_price, "exit_price")
        _non_negative_decimal(self.entry_fees, "entry_fees")
        _non_negative_decimal(self.exit_fees, "exit_fees")
        object.__setattr__(
            self, "entry_timestamp", as_utc(self.entry_timestamp, "entry_timestamp")
        )
        object.__setattr__(
            self, "exit_timestamp", as_utc(self.exit_timestamp, "exit_timestamp")
        )
        if self.exit_timestamp < self.entry_timestamp:
            raise ValueError("exit_timestamp cannot be before entry_timestamp")


@dataclass(frozen=True, slots=True)
class EquityPoint:
    timestamp: datetime
    cash: Decimal
    position_value: Decimal
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal

    def __post_init__(self) -> None:
        _non_negative_decimal(self.cash, "cash")
        _non_negative_decimal(self.position_value, "position_value")
        _non_negative_decimal(self.equity, "equity")
        object.__setattr__(self, "timestamp", as_utc(self.timestamp, "timestamp"))
