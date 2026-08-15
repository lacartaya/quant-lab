from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.analytics import METRICS_VERSION, AnalyticsConfiguration, analyze_backtest
from quant.backtest import (
    BacktestConfiguration,
    BacktestResult,
    EquityPoint,
    ZeroFeeModel,
    ZeroSlippageModel,
)

NOW = datetime(2024, 1, 1, tzinfo=UTC)


def result_with_equities(equities: list[str]) -> BacktestResult:
    backtest_configuration = BacktestConfiguration(
        Decimal("100"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
    )
    points = tuple(
        EquityPoint(
            NOW + timedelta(days=index),
            Decimal(equity),
            Decimal(0),
            Decimal(equity),
            Decimal(0),
            Decimal(0),
        )
        for index, equity in enumerate(equities)
    )
    return BacktestResult(
        backtest_configuration,
        Decimal("100"),
        Decimal(equities[-1]) if equities else Decimal("100"),
        Decimal(equities[-1]) if equities else Decimal("100"),
        (),
        (),
        (),
        (),
        points,
        None,
        (),
        (),
    )


def test_service_populates_metric_set_deterministically() -> None:
    result = result_with_equities(["100", "120", "90", "110"])
    configuration = AnalyticsConfiguration(252)
    first = analyze_backtest(result, configuration)
    second = analyze_backtest(result, configuration)
    assert first == second
    assert first.total_return == pytest.approx(0.10)
    assert first.max_drawdown == pytest.approx(-0.25)
    assert first.trade_count == 0
    assert first.win_rate is None
    assert METRICS_VERSION == "metrics-v1"


def test_constant_equity_has_zero_risk_but_undefined_ratios() -> None:
    metrics = analyze_backtest(
        result_with_equities(["100", "100", "100"]),
        AnalyticsConfiguration(252),
    )
    assert metrics.total_return == 0.0
    assert metrics.max_drawdown == 0.0
    assert metrics.volatility == 0.0
    assert metrics.sharpe is None
    assert metrics.sortino is None
    assert metrics.calmar is None


def test_empty_equity_curve_is_rejected() -> None:
    with pytest.raises(ValueError, match="equity curve"):
        analyze_backtest(result_with_equities([]), AnalyticsConfiguration(252))


@pytest.mark.parametrize("periods", [0, -1])
def test_invalid_annualization_is_rejected(periods: int) -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        AnalyticsConfiguration(periods)
