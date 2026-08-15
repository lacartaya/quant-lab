from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from quant.analytics import AnalyticsConfiguration
from quant.application.experiments.registry import (
    UnsupportedVersionError,
    build_strategy,
    reconstruct_configurations,
    serialize_execution_configuration,
)
from quant.backtest import (
    BacktestConfiguration,
    BasisPointsSlippageModel,
    PercentageFeeModel,
)
from quant.domain import StrategyVersion
from quant.strategies import MovingAverageTrendStrategy


def strategy_version(algorithm_key: str = "moving_average_trend") -> StrategyVersion:
    return StrategyVersion(
        id=uuid4(),
        strategy_id=uuid4(),
        version="v1",
        git_commit="abc123",
        algorithm_key=algorithm_key,
        parameters={"short_window": 2, "long_window": 3},
        created_at=datetime(2026, 8, 15, tzinfo=UTC),
    )


def test_strategy_is_reconstructed_only_from_persisted_parameters() -> None:
    strategy = build_strategy(strategy_version())

    assert isinstance(strategy, MovingAverageTrendStrategy)
    assert strategy.parameters.short_window == 2
    assert strategy.parameters.long_window == 3


def test_unknown_strategy_algorithm_fails_explicitly() -> None:
    with pytest.raises(UnsupportedVersionError, match="unsupported strategy"):
        build_strategy(strategy_version("missing-v1"))


def test_execution_configuration_round_trip_preserves_all_behavioral_values() -> None:
    original_backtest = BacktestConfiguration(
        initial_cash=Decimal("10000"),
        position_fraction=Decimal("0.75"),
        fee_model=PercentageFeeModel(Decimal("0.001")),
        slippage_model=BasisPointsSlippageModel(Decimal("10")),
    )
    original_analytics = AnalyticsConfiguration(
        periods_per_year=365,
        annual_risk_free_rate=Decimal("0.025"),
    )

    stored = serialize_execution_configuration(original_backtest, original_analytics)
    backtest, analytics = reconstruct_configurations(stored)

    assert backtest == original_backtest
    assert analytics == original_analytics


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("engine_version",), "backtest-engine-v0", "backtest engine"),
        (("analytics", "version"), "metrics-v0", "analytics version"),
        (("fee", "version"), "fee-v0", "fee model"),
        (("slippage", "version"), "slippage-v0", "slippage model"),
    ],
)
def test_unsupported_historical_versions_are_never_silently_substituted(
    path: tuple[str, ...], value: str, message: str
) -> None:
    stored = serialize_execution_configuration(
        BacktestConfiguration(
            Decimal("100"),
            Decimal("1"),
            PercentageFeeModel(Decimal("0.001")),
            BasisPointsSlippageModel(Decimal("10")),
        ),
        AnalyticsConfiguration(252),
    )
    target: dict[str, object] = stored
    for key in path[:-1]:
        nested = target[key]
        assert isinstance(nested, dict)
        target = nested
    target[path[-1]] = value

    with pytest.raises(UnsupportedVersionError, match=message):
        reconstruct_configurations(stored)
