import math

import pytest

from quant.analytics import (
    annualized_volatility,
    calmar_ratio,
    compound_annual_growth_rate,
    maximum_drawdown,
    periodic_returns,
    sharpe_ratio,
    sortino_ratio,
    total_return,
)


def test_total_return_golden_example() -> None:
    assert total_return(100.0, 110.0) == pytest.approx(0.10)


def test_periodic_returns_use_equity_changes() -> None:
    assert periodic_returns([100.0, 110.0, 99.0]) == pytest.approx((0.1, -0.1))


def test_maximum_drawdown_golden_example() -> None:
    assert maximum_drawdown([100.0, 120.0, 90.0, 110.0]) == pytest.approx(-0.25)


def test_volatility_uses_sample_standard_deviation() -> None:
    expected = math.sqrt(0.02) * math.sqrt(4)
    assert annualized_volatility([0.1, -0.1], 4) == pytest.approx(expected)


def test_sharpe_golden_example() -> None:
    # Mean = 0.10, sample standard deviation = 0.10, annualization sqrt(4) = 2.
    assert sharpe_ratio([0.1, 0.2, 0.0], 4, 0.0) == pytest.approx(2.0)


def test_sortino_uses_all_periods_in_downside_deviation() -> None:
    expected = (0.2 / 3) / math.sqrt(0.01 / 3) * math.sqrt(4)
    assert sortino_ratio([0.1, -0.1, 0.2], 4, 0.0) == pytest.approx(expected)


def test_cagr_and_calmar() -> None:
    cagr = compound_annual_growth_rate(100.0, 121.0, 2, 2)
    assert cagr == pytest.approx(0.21)
    assert calmar_ratio(cagr, -0.1) == pytest.approx(2.1)


def test_undefined_statistical_values_are_none() -> None:
    assert annualized_volatility([], 252) is None
    assert annualized_volatility([0.1], 252) is None
    assert sharpe_ratio([0.0, 0.0], 252, 0.0) is None
    assert sortino_ratio([0.1, 0.2], 252, 0.0) is None
    assert calmar_ratio(0.1, 0.0) is None
    assert compound_annual_growth_rate(100.0, 110.0, 0, 252) is None


def test_invalid_prior_equity_is_rejected() -> None:
    with pytest.raises(ValueError, match="prior equity"):
        periodic_returns([100.0, 0.0, 110.0])
