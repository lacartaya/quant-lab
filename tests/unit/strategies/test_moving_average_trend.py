from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.domain import (
    AdjustmentPolicy,
    HistoricalDataset,
    MarketBar,
    SignalAction,
)
from quant.strategies import (
    BASELINE_MOVING_AVERAGE_PARAMETERS,
    ExecutableStrategy,
    MovingAverageParameters,
    MovingAverageTrendStrategy,
)

START = datetime(2024, 1, 1, tzinfo=UTC)


def dataset_from_closes(closes: list[str]) -> HistoricalDataset:
    bars = [
        MarketBar(
            timestamp=START + timedelta(days=index),
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=Decimal("100"),
        )
        for index, close in enumerate(closes)
    ]
    return HistoricalDataset.from_bars(
        market="Test market",
        instrument="TEST",
        timeframe="daily",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=bars,
    )


@pytest.mark.parametrize(
    ("short_window", "long_window"),
    [(0, 3), (1, 0), (3, 3), (4, 3)],
)
def test_invalid_parameters_are_rejected(
    short_window: int, long_window: int
) -> None:
    with pytest.raises(ValueError):
        MovingAverageParameters(short_window, long_window)


def test_parameters_are_typed_and_serializable_for_strategy_version() -> None:
    parameters = MovingAverageParameters(2, 3)
    assert parameters.as_dict() == {"short_window": 2, "long_window": 3}
    assert BASELINE_MOVING_AVERAGE_PARAMETERS.as_dict() == {
        "short_window": 50,
        "long_window": 200,
    }


def test_strategy_implements_executable_contract_with_stable_key() -> None:
    algorithm: ExecutableStrategy = MovingAverageTrendStrategy(
        MovingAverageParameters(2, 3)
    )
    assert algorithm.strategy_key == "moving_average_trend"


def test_warm_up_produces_no_signal() -> None:
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))
    assert strategy.generate_signals(dataset_from_closes(["1", "2"])) == ()


def test_short_average_above_long_average_is_long() -> None:
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))
    signals = strategy.generate_signals(dataset_from_closes(["1", "2", "3"]))
    assert [signal.action for signal in signals] == [SignalAction.LONG]


@pytest.mark.parametrize("closes", [["3", "2", "1"], ["1", "1", "1"]])
def test_short_average_not_above_long_average_is_flat(closes: list[str]) -> None:
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))
    signals = strategy.generate_signals(dataset_from_closes(closes))
    assert [signal.action for signal in signals] == [SignalAction.FLAT]


def test_crossover_occurs_at_expected_completed_bar() -> None:
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))
    signals = strategy.generate_signals(dataset_from_closes(["3", "2", "1", "4"]))
    assert [(signal.timestamp, signal.action) for signal in signals] == [
        (START + timedelta(days=2), SignalAction.FLAT),
        (START + timedelta(days=3), SignalAction.LONG),
    ]


def test_cross_under_occurs_at_expected_completed_bar() -> None:
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))
    signals = strategy.generate_signals(dataset_from_closes(["1", "2", "3", "0"]))
    assert [(signal.timestamp, signal.action) for signal in signals] == [
        (START + timedelta(days=2), SignalAction.LONG),
        (START + timedelta(days=3), SignalAction.FLAT),
    ]


def test_golden_sma_example_is_human_verifiable() -> None:
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))
    signals = strategy.generate_signals(
        dataset_from_closes(["1", "2", "3", "4", "5", "6"])
    )
    # Eligible (short SMA, long SMA) pairs are:
    # (2.5, 2), (3.5, 3), (4.5, 4), and (5.5, 5).
    assert [signal.action for signal in signals] == [SignalAction.LONG] * 4
    assert [signal.timestamp for signal in signals] == [
        START + timedelta(days=index) for index in range(2, 6)
    ]


def test_signal_generation_is_deterministic_and_does_not_mutate_input() -> None:
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))
    dataset = dataset_from_closes(["3", "2", "1", "4", "5"])
    original_bars = dataset.bars
    first_run = strategy.generate_signals(dataset)
    second_run = strategy.generate_signals(dataset)
    assert first_run == second_run
    assert dataset.bars is original_bars


def test_future_bar_cannot_change_an_earlier_signal() -> None:
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))
    low_future = dataset_from_closes(["3", "2", "1", "4", "0"])
    high_future = dataset_from_closes(["3", "2", "1", "4", "100"])
    cutoff = START + timedelta(days=3)
    low_prefix = tuple(
        signal
        for signal in strategy.generate_signals(low_future)
        if signal.timestamp <= cutoff
    )
    high_prefix = tuple(
        signal
        for signal in strategy.generate_signals(high_future)
        if signal.timestamp <= cutoff
    )
    assert low_prefix == high_prefix
    assert [signal.action for signal in low_prefix] == [
        SignalAction.FLAT,
        SignalAction.LONG,
    ]
