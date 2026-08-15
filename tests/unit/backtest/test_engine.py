from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.backtest import (
    BacktestConfiguration,
    BacktestEngine,
    BasisPointsSlippageModel,
    OrderSide,
    PercentageFeeModel,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import (
    AdjustmentPolicy,
    HistoricalDataset,
    MarketBar,
    Signal,
    SignalAction,
)

START = datetime(2024, 1, 1, tzinfo=UTC)


class ControlledStrategy:
    strategy_key = "controlled"

    def __init__(self, actions: dict[datetime, SignalAction]) -> None:
        self.actions = actions

    def generate_signals(self, dataset: HistoricalDataset) -> Sequence[Signal]:
        available = {bar.timestamp for bar in dataset.bars}
        return tuple(
            Signal(timestamp, action)
            for timestamp, action in sorted(self.actions.items())
            if timestamp in available
        )


def make_dataset(rows: list[tuple[str, str]]) -> HistoricalDataset:
    bars = []
    for index, (open_price, close_price) in enumerate(rows):
        open_value = Decimal(open_price)
        close_value = Decimal(close_price)
        bars.append(
            MarketBar(
                START + timedelta(days=index),
                open_value,
                max(open_value, close_value),
                min(open_value, close_value),
                close_value,
                Decimal("1000"),
            )
        )
    return HistoricalDataset.from_bars(
        market="Test market",
        instrument="TEST",
        timeframe="daily",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=bars,
    )


def configuration(
    *, costs: bool = False, initial_cash: str = "100"
) -> BacktestConfiguration:
    return BacktestConfiguration(
        initial_cash=Decimal(initial_cash),
        position_fraction=Decimal("1"),
        fee_model=PercentageFeeModel(Decimal("0.01"))
        if costs
        else ZeroFeeModel(),
        slippage_model=BasisPointsSlippageModel(Decimal("10"))
        if costs
        else ZeroSlippageModel(),
    )


def test_round_trip_golden_backtest() -> None:
    dataset = make_dataset(
        [("10", "10"), ("10", "11"), ("12", "13"), ("14", "12"), ("11", "10")]
    )
    strategy = ControlledStrategy(
        {
            START + timedelta(days=1): SignalAction.LONG,
            START + timedelta(days=3): SignalAction.FLAT,
        }
    )
    result = BacktestEngine().run(dataset, strategy, configuration())
    order_details = [
        (order.timestamp, order.side, order.quantity) for order in result.orders
    ]
    assert order_details == [
        (START + timedelta(days=2), OrderSide.BUY, 8),
        (START + timedelta(days=4), OrderSide.SELL, 8),
    ]
    assert [fill.fill_price for fill in result.fills] == [Decimal("12"), Decimal("11")]
    assert result.trades[0].realized_pnl == Decimal("-8")
    assert result.final_cash == Decimal("92")
    assert result.final_equity == Decimal("92")
    assert result.open_position is None


def test_fill_uses_next_open_and_not_signal_close_or_later_close() -> None:
    strategy = ControlledStrategy({START + timedelta(days=1): SignalAction.LONG})
    first = make_dataset([("10", "10"), ("10", "11"), ("12", "13"), ("14", "15")])
    changed = make_dataset([("10", "10"), ("10", "11"), ("12", "99"), ("999", "999")])
    first_result = BacktestEngine().run(first, strategy, configuration())
    changed_result = BacktestEngine().run(changed, strategy, configuration())
    assert first_result.fills[0].reference_price == Decimal("12")
    assert changed_result.fills[0] == first_result.fills[0]


def test_final_signal_is_recorded_but_not_executed() -> None:
    dataset = make_dataset([("10", "10"), ("10", "11")])
    signal_time = START + timedelta(days=1)
    result = BacktestEngine().run(
        dataset,
        ControlledStrategy({signal_time: SignalAction.LONG}),
        configuration(),
    )
    assert result.orders == ()
    assert result.unexecuted_signals == (Signal(signal_time, SignalAction.LONG),)


def test_open_position_is_marked_without_forced_liquidation() -> None:
    dataset = make_dataset([("10", "10"), ("10", "11"), ("12", "15")])
    result = BacktestEngine().run(
        dataset,
        ControlledStrategy({START + timedelta(days=1): SignalAction.LONG}),
        configuration(),
    )
    assert result.trades == ()
    assert result.open_position is not None
    assert result.open_position.market_value == Decimal("120")
    assert result.open_position.unrealized_pnl == Decimal("24")
    assert result.final_cash == Decimal("4")
    assert result.final_equity == Decimal("124")


def test_insufficient_capital_skips_execution_without_negative_cash() -> None:
    dataset = make_dataset([("10", "10"), ("10", "11"), ("100", "100")])
    signal = Signal(START + timedelta(days=1), SignalAction.LONG)
    result = BacktestEngine().run(
        dataset,
        ControlledStrategy({signal.timestamp: signal.action}),
        configuration(initial_cash="10"),
    )
    assert result.orders == ()
    assert result.skipped_signals == (signal,)
    assert result.final_cash == Decimal("10")


def test_costs_reduce_equity_and_results_are_deterministic() -> None:
    dataset = make_dataset(
        [("10", "10"), ("10", "11"), ("12", "13"), ("14", "14"), ("15", "15")]
    )
    strategy = ControlledStrategy(
        {
            START + timedelta(days=1): SignalAction.LONG,
            START + timedelta(days=3): SignalAction.FLAT,
        }
    )
    original_bars = dataset.bars
    original_actions = dict(strategy.actions)
    engine = BacktestEngine()
    free = engine.run(dataset, strategy, configuration())
    costly = engine.run(dataset, strategy, configuration(costs=True))
    assert costly.final_equity < free.final_equity
    assert engine.run(dataset, strategy, configuration()) == free
    assert dataset.bars is original_bars
    assert strategy.actions == original_actions


@pytest.mark.parametrize(
    ("initial_cash", "fraction"),
    [("0", "1"), ("100", "0"), ("100", "1.01")],
)
def test_invalid_configuration_is_rejected(
    initial_cash: str, fraction: str
) -> None:
    with pytest.raises(ValueError):
        BacktestConfiguration(
            Decimal(initial_cash),
            Decimal(fraction),
            ZeroFeeModel(),
            ZeroSlippageModel(),
        )
