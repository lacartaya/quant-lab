from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant.backtest import Fill, OrderSide, Portfolio

NOW = datetime(2024, 1, 1, tzinfo=UTC)


def fill(
    side: OrderSide,
    price: str,
    fees: str,
    timestamp: datetime = NOW,
) -> Fill:
    return Fill(
        "ORDER",
        timestamp,
        side,
        10,
        Decimal(price),
        Decimal(price),
        Decimal(fees),
        Decimal(0),
    )


def test_portfolio_accounts_for_open_and_closed_position() -> None:
    portfolio = Portfolio(Decimal("2000"))
    portfolio.apply_buy(fill(OrderSide.BUY, "100", "10"))
    point = portfolio.mark(NOW, Decimal("110"))
    assert point.cash == Decimal("990")
    assert point.position_value == Decimal("1100")
    assert point.equity == Decimal("2090")
    assert point.unrealized_pnl == Decimal("90")

    trade = portfolio.apply_sell(
        fill(OrderSide.SELL, "120", "12", NOW + timedelta(days=1))
    )
    assert trade.realized_pnl == Decimal("178")
    assert portfolio.cash == Decimal("2178")
    final_point = portfolio.mark(NOW + timedelta(days=1), Decimal("120"))
    assert final_point.realized_pnl == Decimal("178")
