from collections.abc import Sequence
from decimal import Decimal

from quant.backtest import Trade


def trade_statistics(
    trades: Sequence[Trade],
) -> tuple[float | None, float | None, float | None, int]:
    trade_count = len(trades)
    if trade_count == 0:
        return None, None, None, 0
    profits = [trade.realized_pnl for trade in trades if trade.realized_pnl > 0]
    losses = [trade.realized_pnl for trade in trades if trade.realized_pnl < 0]
    win_rate = len(profits) / trade_count
    gross_profit = sum(profits, Decimal(0))
    gross_loss = sum(losses, Decimal(0))
    profit_factor = (
        float(gross_profit / abs(gross_loss)) if gross_loss < 0 else None
    )
    expectancy = float(
        sum((trade.realized_pnl for trade in trades), Decimal(0))
        / Decimal(trade_count)
    )
    return profit_factor, win_rate, expectancy, trade_count
