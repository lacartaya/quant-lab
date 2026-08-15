import random
from decimal import Decimal

import pytest

from quant.domain import MetricSet
from quant.validation import (
    MAX_SIMULATION_COUNT,
    MonteCarloConfiguration,
    MonteCarloPathSummary,
    SamplingMethod,
    maximum_consecutive_losses,
    percentile,
    simulate_trade_bootstrap,
    summarize_bootstrap_path,
    summarize_monte_carlo,
    trade_return_observations,
)


def configuration(*, seed: int = 42, count: int = 4) -> MonteCarloConfiguration:
    return MonteCarloConfiguration(
        simulation_count=count,
        random_seed=seed,
        confidence_percentiles=(Decimal("0.05"), Decimal("0.50"), Decimal("0.95")),
        sampling_method=SamplingMethod.TRADE_BOOTSTRAP,
    )


def test_configuration_rejects_invalid_or_excessive_simulation_counts() -> None:
    with pytest.raises(ValueError, match="positive"):
        configuration(count=0)
    with pytest.raises(ValueError, match="maximum"):
        configuration(count=MAX_SIMULATION_COUNT + 1)


def test_trade_returns_use_net_pnl_over_entry_capital_basis() -> None:
    trades = (
        {
            "entry_price": "100",
            "quantity": 10,
            "entry_fees": "10",
            "realized_pnl": "101",
        },
        {
            "entry_price": "50",
            "quantity": 2,
            "entry_fees": "0",
            "realized_pnl": "-10",
        },
    )

    assert trade_return_observations(trades) == (Decimal("0.1"), Decimal("-0.1"))


def test_trade_bootstrap_requires_two_completed_trades() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        trade_return_observations(
            (
                {
                    "entry_price": "100",
                    "quantity": 1,
                    "entry_fees": "0",
                    "realized_pnl": "1",
                },
            )
        )


def test_seed_42_bootstrap_has_exact_golden_paths() -> None:
    paths = simulate_trade_bootstrap(
        (Decimal("0.1"), Decimal("-0.1")), Decimal("100"), configuration()
    )

    assert tuple(path.final_equity for path in paths) == (
        Decimal("121"),
        Decimal("99"),
        Decimal("121"),
        Decimal("121"),
    )
    assert tuple(path.max_drawdown for path in paths) == (
        Decimal("0"),
        Decimal("-0.1"),
        Decimal("0"),
        Decimal("0"),
    )


def test_local_seed_is_deterministic_and_does_not_modify_global_rng() -> None:
    observations = (Decimal("0.1"), Decimal("-0.1"), Decimal("0.05"))
    random.seed(999)
    expected_next = random.random()
    random.seed(999)

    first = simulate_trade_bootstrap(observations, Decimal("100"), configuration())
    second = simulate_trade_bootstrap(observations, Decimal("100"), configuration())

    assert first == second
    assert random.random() == expected_next
    assert simulate_trade_bootstrap(
        observations, Decimal("100"), configuration(seed=43)
    ) != first


def test_path_drawdown_and_losing_streak_are_manually_verifiable() -> None:
    path = summarize_bootstrap_path(
        1,
        Decimal("100"),
        (Decimal("0.10"), Decimal("-0.20"), Decimal("0.05")),
    )

    assert path.final_equity == Decimal("92.4")
    assert path.total_return == Decimal("-0.076")
    assert path.max_drawdown == Decimal("-0.20")
    assert maximum_consecutive_losses(
        (
            Decimal("0.01"),
            Decimal("-0.01"),
            Decimal("-0.02"),
            Decimal("-0.03"),
            Decimal("0.02"),
            Decimal("-0.01"),
        )
    ) == 3
    assert maximum_consecutive_losses(
        (Decimal("-0.1"), Decimal("0"), Decimal("-0.1"))
    ) == 1


def test_percentile_uses_linear_n_minus_one_interpolation() -> None:
    values = tuple(Decimal(value) for value in (0, 10, 20, 30))

    assert percentile(values, Decimal("0.25")) == Decimal("7.5")
    assert percentile(values, Decimal("0.50")) == Decimal("15")


def test_distribution_frequencies_are_empirical_and_thresholds_are_explicit() -> None:
    paths = tuple(
        MonteCarloPathSummary(
            index,
            Decimal("100") * (Decimal(1) + result),
            minimum,
            result,
            drawdown,
            index,
        )
        for index, result, minimum, drawdown in (
            (1, Decimal("0.10"), Decimal("100"), Decimal("-0.10")),
            (2, Decimal("-0.05"), Decimal("90"), Decimal("-0.15")),
            (3, Decimal("-0.20"), Decimal("40"), Decimal("-0.25")),
            (4, Decimal("0.03"), Decimal("99"), Decimal("-0.02")),
        )
    )
    config = MonteCarloConfiguration(
        4,
        42,
        (Decimal("0.5"),),
        SamplingMethod.TRADE_BOOTSTRAP,
        drawdown_threshold=Decimal("-0.20"),
        ruin_equity_fraction=Decimal("0.5"),
    )

    summary = summarize_monte_carlo(paths, Decimal("100"), config, 0.03)

    assert summary.empirical_loss_frequency == 0.5
    assert summary.empirical_severe_drawdown_frequency == 0.25
    assert summary.empirical_ruin_frequency == 0.25
    assert summary.historical_total_return_percentile == 0.75


def test_analysis_does_not_calculate_or_mutate_historical_metrics() -> None:
    metrics = MetricSet(total_return=0.1, trade_count=2)
    before = metrics
    simulate_trade_bootstrap(
        (Decimal("0.1"), Decimal("-0.1")), Decimal("100"), configuration()
    )
    assert metrics == before
