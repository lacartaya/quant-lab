from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class PaperOrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class PaperOrderType(StrEnum):
    MARKET = "market"


class PaperTimeInForce(StrEnum):
    DAY = "day"


@dataclass(frozen=True, slots=True)
class AlpacaPaperAccount:
    account_id: str
    account_number: str
    status: str
    currency: str
    cash: Decimal
    buying_power: Decimal
    equity: Decimal
    portfolio_value: Decimal
    trading_blocked: bool
    pattern_day_trader: bool
    simulated: bool = True


@dataclass(frozen=True, slots=True)
class SubmitAlpacaPaperOrder:
    symbol: str
    quantity: Decimal
    side: PaperOrderSide
    order_type: PaperOrderType
    time_in_force: PaperTimeInForce
    client_order_id: str

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.symbol.isascii():
            raise ValueError("paper order symbol is required")
        if self.quantity <= 0:
            raise ValueError("paper order quantity must be positive")
        if not self.client_order_id.strip() or len(self.client_order_id) > 128:
            raise ValueError("client_order_id must contain 1 to 128 characters")


@dataclass(frozen=True, slots=True)
class AlpacaPaperOrder:
    order_id: str
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    time_in_force: str
    status: str
    quantity: Decimal
    filled_quantity: Decimal
    filled_average_price: Decimal | None
    submitted_at: datetime | None
    filled_at: datetime | None
    simulated: bool = True


@dataclass(frozen=True, slots=True)
class AlpacaPaperPosition:
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal
    market_value: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    simulated: bool = True


@dataclass(frozen=True, slots=True)
class AlpacaPaperFill:
    activity_id: str
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    transaction_time: datetime
    activity_type: str
    simulated: bool = True
