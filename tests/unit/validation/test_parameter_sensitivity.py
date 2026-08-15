from decimal import Decimal

import pytest

from quant.backtest import (
    BacktestConfiguration,
    BacktestResult,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import MetricSet
from quant.validation import (
    ParameterCandidateResult,
    ParameterSensitivityConfiguration,
    ParameterSpaceTooLarge,
    generate_parameter_combinations,
    relative_parameter_distance,
    summarize_parameter_sensitivity,
)


def configuration(
    short: tuple[int, ...] = (2, 3),
    long: tuple[int, ...] = (3, 4),
    maximum: int = 10,
) -> ParameterSensitivityConfiguration:
    return ParameterSensitivityConfiguration(
        {"short_window": short, "long_window": long}, maximum
    )


def test_parameter_grid_has_canonical_valid_order() -> None:
    space = generate_parameter_combinations(
        configuration(), {"short_window": 2, "long_window": 4}
    )

    assert [dict(item.values) for item in space.combinations] == [
        {"long_window": 3, "short_window": 2},
        {"long_window": 4, "short_window": 2},
        {"long_window": 4, "short_window": 3},
    ]
    assert [item.id for item in space.combinations] == [
        "COMBINATION-001",
        "COMBINATION-002",
        "COMBINATION-003",
    ]
    assert space.requested_count == 4
    assert space.invalid_count == 1
    assert sum(item.is_baseline for item in space.combinations) == 1


def test_missing_baseline_is_added_exactly_once() -> None:
    space = generate_parameter_combinations(
        configuration(short=(2,), long=(3,), maximum=2),
        {"short_window": 2, "long_window": 4},
    )
    assert space.baseline_added
    assert [dict(item.values) for item in space.combinations] == [
        {"long_window": 3, "short_window": 2},
        {"short_window": 2, "long_window": 4},
    ]
    assert sum(item.is_baseline for item in space.combinations) == 1


def test_maximum_guard_fails_before_truncating() -> None:
    with pytest.raises(ParameterSpaceTooLarge, match="requested 6"):
        generate_parameter_combinations(
            configuration(short=(1, 2, 3), long=(4, 5), maximum=5),
            {"short_window": 2, "long_window": 4},
        )


def test_relative_distance_is_interpretable() -> None:
    assert relative_parameter_distance(
        {"short_window": 55, "long_window": 180},
        {"short_window": 50, "long_window": 200},
    ) == {"long_window": -0.1, "short_window": 0.1}


def test_fragile_surface_reports_neighbor_delta_without_rejection() -> None:
    config = configuration(short=(1, 2, 3), long=(3, 4, 5), maximum=9)
    space = generate_parameter_combinations(
        config, {"short_window": 2, "long_window": 4}
    )
    sharpes = {
        (1, 4): 0.1,
        (2, 3): 0.2,
        (2, 4): 2.0,
        (2, 5): 0.0,
        (3, 4): 0.1,
    }
    results = results_for_space(space, sharpes)
    summary = summarize_parameter_sensitivity(space, results, config)

    assert summary.neighbor_count == 4
    assert summary.neighbor_median_sharpe == pytest.approx(0.1)
    assert summary.neighbor_min_sharpe == 0.0
    assert summary.neighbor_max_sharpe == 0.2
    assert summary.sharpe_neighbor_delta == pytest.approx(1.9)


def test_stable_surface_has_low_neighbor_dispersion_and_delta() -> None:
    config = configuration(short=(1, 2, 3), long=(3, 4, 5), maximum=9)
    space = generate_parameter_combinations(
        config, {"short_window": 2, "long_window": 4}
    )
    sharpes = {
        (1, 4): 0.95,
        (2, 3): 1.04,
        (2, 4): 1.0,
        (2, 5): 0.92,
        (3, 4): 1.03,
    }
    results = results_for_space(space, sharpes, default_sharpe=1.0)
    summary = summarize_parameter_sensitivity(space, results, config)

    assert summary.neighbor_count == 4
    assert summary.neighbor_median_sharpe == pytest.approx(0.99)
    assert summary.sharpe_neighbor_delta == pytest.approx(0.01)
    assert summary.sharpe_dispersion is not None
    assert summary.sharpe_dispersion < 0.1


def test_profitability_and_baseline_relative_ratios() -> None:
    config = configuration(short=(1, 2, 3, 4, 5), long=(6,), maximum=5)
    space = generate_parameter_combinations(
        config, {"short_window": 3, "long_window": 6}
    )
    returns = (0.10, 0.05, -0.02, 0.03, -0.07)
    results = tuple(
        candidate(item, total_return, float(item.index))
        for item, total_return in zip(space.combinations, returns, strict=True)
    )
    summary = summarize_parameter_sensitivity(space, results, config)

    assert summary.profitable_combination_count == 3
    assert summary.profitable_combination_ratio == 0.6
    assert summary.parameter_combinations_requested == 5
    assert summary.parameter_combinations_executed == 5


def results_for_space(
    space: object,
    sharpes: dict[tuple[int, int], float],
    default_sharpe: float = 0.5,
) -> tuple[ParameterCandidateResult, ...]:
    from quant.validation import ParameterSpace

    assert isinstance(space, ParameterSpace)
    return tuple(
        candidate(
            combination,
            0.01 * combination.index,
            sharpes.get(
                (
                    combination.values["short_window"],
                    combination.values["long_window"],
                ),
                default_sharpe,
            ),
        )
        for combination in space.combinations
    )


def candidate(
    combination: object, total_return: float, sharpe: float
) -> ParameterCandidateResult:
    from quant.validation import ParameterCombination

    assert isinstance(combination, ParameterCombination)
    config = BacktestConfiguration(
        Decimal("100"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
    )
    backtest = BacktestResult(
        config,
        Decimal("100"),
        Decimal("100"),
        Decimal("100"),
        (),
        (),
        (),
        (),
        (),
        None,
        (),
        (),
    )
    metrics = MetricSet(
        total_return=total_return,
        sharpe=sharpe,
        max_drawdown=-0.1,
        trade_count=1,
    )
    baseline = {"short_window": 2, "long_window": 4}
    return ParameterCandidateResult(
        combination,
        metrics,
        backtest,
        relative_parameter_distance(combination.values, baseline),
    )
