from datetime import datetime
from decimal import Context, Decimal, localcontext

from quant.backtest.models import EquityPoint, Fill, OrderSide, Position, Trade


class Portfolio:
    """Mutable accounting state owned exclusively by one backtest run."""

    def __init__(self, initial_cash: Decimal) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.cash = initial_cash
        self.realized_pnl = Decimal(0)
        self._quantity = 0
        self._entry_price: Decimal | None = None
        self._entry_timestamp: datetime | None = None
        self._entry_fees = Decimal(0)

    @property
    def is_long(self) -> bool:
        return self._quantity > 0

    @property
    def quantity(self) -> int:
        return self._quantity

    def apply_buy(self, fill: Fill) -> None:
        if fill.side is not OrderSide.BUY:
            raise ValueError("opening fill must be BUY")
        if self.is_long:
            raise ValueError("pyramiding is not supported")
        with localcontext(Context(prec=64)):
            total_cost = Decimal(fill.quantity) * fill.fill_price + fill.fees
            if total_cost > self.cash:
                raise ValueError("buy fill would make cash negative")
            self.cash -= total_cost
        self._quantity = fill.quantity
        self._entry_price = fill.fill_price
        self._entry_timestamp = fill.timestamp
        self._entry_fees = fill.fees

    def apply_sell(self, fill: Fill) -> Trade:
        if fill.side is not OrderSide.SELL:
            raise ValueError("closing fill must be SELL")
        if not self.is_long or fill.quantity != self._quantity:
            raise ValueError("sell fill must close the entire position")
        if self._entry_price is None or self._entry_timestamp is None:
            raise RuntimeError("long position is missing entry lineage")
        with localcontext(Context(prec=64)):
            proceeds = Decimal(fill.quantity) * fill.fill_price - fill.fees
            realized_pnl = (
                (fill.fill_price - self._entry_price) * Decimal(fill.quantity)
                - self._entry_fees
                - fill.fees
            )
            self.cash += proceeds
            self.realized_pnl += realized_pnl
        trade = Trade(
            entry_timestamp=self._entry_timestamp,
            entry_price=self._entry_price,
            exit_timestamp=fill.timestamp,
            exit_price=fill.fill_price,
            quantity=fill.quantity,
            entry_fees=self._entry_fees,
            exit_fees=fill.fees,
            realized_pnl=realized_pnl,
        )
        self._quantity = 0
        self._entry_price = None
        self._entry_timestamp = None
        self._entry_fees = Decimal(0)
        return trade

    def position(self, market_price: Decimal) -> Position | None:
        if market_price <= 0:
            raise ValueError("market_price must be positive")
        if not self.is_long:
            return None
        if self._entry_price is None:
            raise RuntimeError("long position is missing entry price")
        with localcontext(Context(prec=64)):
            market_value = Decimal(self._quantity) * market_price
            unrealized_pnl = (
                (market_price - self._entry_price) * Decimal(self._quantity)
                - self._entry_fees
            )
        return Position(
            quantity=self._quantity,
            average_entry_price=self._entry_price,
            entry_fees=self._entry_fees,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
        )

    def mark(self, timestamp: datetime, market_price: Decimal) -> EquityPoint:
        position = self.position(market_price)
        position_value = position.market_value if position is not None else Decimal(0)
        unrealized = position.unrealized_pnl if position is not None else Decimal(0)
        with localcontext(Context(prec=64)):
            equity = self.cash + position_value
        return EquityPoint(
            timestamp=timestamp,
            cash=self.cash,
            position_value=position_value,
            equity=equity,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=unrealized,
        )
