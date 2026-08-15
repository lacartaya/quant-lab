from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.analytics import trade_statistics
from quant.backtest import Trade

NOW = datetime(2024, 1, 1, tzinfo=UTC)


def trade(pnl: str) -> Trade:
    return Trade(
        NOW,
        Decimal("10"),
        NOW + timedelta(days=1),
        Decimal("11"),
        1,
        Decimal(0),
        Decimal(0),
        Decimal(pnl),
    )


def test_trade_metric_golden_examples() -> None:
    profit_factor, win_rate, expectancy, count = trade_statistics(
        [trade("10"), trade("-5"), trade("20")]
    )
    assert profit_factor == pytest.approx(6.0)
    assert win_rate == pytest.approx(2 / 3)
    assert expectancy == pytest.approx(25 / 3)
    assert count == 3


def test_breakeven_counts_as_trade_but_not_win() -> None:
    _, win_rate, expectancy, count = trade_statistics([trade("0")])
    assert win_rate == 0.0
    assert expectancy == 0.0
    assert count == 1


def test_trade_edge_cases() -> None:
    assert trade_statistics([]) == (None, None, None, 0)
    assert trade_statistics([trade("10")])[0] is None
    assert trade_statistics([trade("-10")]) == (0.0, 0.0, -10.0, 1)
