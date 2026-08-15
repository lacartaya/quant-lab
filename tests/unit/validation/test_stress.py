from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from quant.application.experiments import apply_stress_scenario
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
    StrategyVersion,
)
from quant.validation import StressScenario, StressType

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FixedSignals:
    strategy_key = "fixed"

    def __init__(self, signals: tuple[Signal, ...]) -> None:
        self.signals = signals

    def generate_signals(self, dataset: HistoricalDataset) -> tuple[Signal, ...]:
        return tuple(
            signal
            for signal in self.signals
            if signal.timestamp <= dataset.bars[-1].timestamp
        )


def version() -> StrategyVersion:
    return StrategyVersion(
        uuid4(),
        uuid4(),
        "v1",
        "abc123",
        "moving_average_trend",
        {"short_window": 2, "long_window": 3},
        NOW,
    )


def test_fee_multiplier_golden_and_zero_fee_edge_case() -> None:
    scenario = StressScenario(
        "STRESS-FEES-2X",
        "Fees doubled",
        StressType.FEE_MULTIPLIER,
        {"multiplier": Decimal("2")},
    )
    stressed, delay, parameters, no_effect = apply_stress_scenario(
        scenario,
        BacktestConfiguration(
            Decimal("1000"),
            Decimal("1"),
            PercentageFeeModel(Decimal("0.001")),
            ZeroSlippageModel(),
        ),
        version(),
    )
    assert isinstance(stressed.fee_model, PercentageFeeModel)
    assert stressed.fee_model.rate == Decimal("0.002")
    assert delay == 0
    assert parameters is None
    assert not no_effect

    source = dataset(("100", "100", "100"))
    strategy = FixedSignals(
        (
            Signal(source.bars[0].timestamp, SignalAction.LONG),
            Signal(source.bars[1].timestamp, SignalAction.FLAT),
        )
    )
    stressed_result = BacktestEngine().run(source, strategy, stressed)
    assert stressed_result.final_equity == Decimal("996.400")

    zero_stressed, _, _, zero_no_effect = apply_stress_scenario(
        scenario,
        BacktestConfiguration(
            Decimal("1000"),
            Decimal("1"),
            ZeroFeeModel(),
            ZeroSlippageModel(),
        ),
        version(),
    )
    assert isinstance(zero_stressed.fee_model, ZeroFeeModel)
    assert zero_no_effect


def test_slippage_multiplier_and_adverse_price_are_directional() -> None:
    slippage = StressScenario(
        "STRESS-SLIPPAGE-3X",
        "Slippage tripled",
        StressType.SLIPPAGE_MULTIPLIER,
        {"multiplier": Decimal("3")},
    )
    stressed, _, _, _ = apply_stress_scenario(
        slippage,
        BacktestConfiguration(
            Decimal("1000"),
            Decimal("1"),
            ZeroFeeModel(),
            BasisPointsSlippageModel(Decimal("10")),
        ),
        version(),
    )
    assert isinstance(stressed.slippage_model, BasisPointsSlippageModel)
    assert stressed.slippage_model.basis_points == Decimal("30")
    assert stressed.slippage_model.apply(
        side=OrderSide.BUY, reference_price=Decimal("100")
    ) == Decimal("100.3")
    assert stressed.slippage_model.apply(
        side=OrderSide.SELL, reference_price=Decimal("100")
    ) == Decimal("99.7")

    adverse = StressScenario(
        "STRESS-ADVERSE-10BPS",
        "Additional adverse fill",
        StressType.ADVERSE_PRICE,
        {"additional_basis_points": Decimal("10")},
    )
    adverse_config, _, _, _ = apply_stress_scenario(adverse, stressed, version())
    assert isinstance(adverse_config.slippage_model, BasisPointsSlippageModel)
    assert adverse_config.slippage_model.basis_points == Decimal("40")


def test_execution_delay_moves_entry_and_exit_and_never_fabricates_fills() -> None:
    source = dataset(("10", "100", "105", "10", "50", "40"))
    strategy = FixedSignals(
        (
            Signal(source.bars[0].timestamp, SignalAction.LONG),
            Signal(source.bars[3].timestamp, SignalAction.FLAT),
        )
    )
    configuration = BacktestConfiguration(
        Decimal("1000"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
    )
    baseline = BacktestEngine().run(source, strategy, configuration)
    delayed = BacktestEngine().run(
        source, strategy, configuration, execution_delay_bars=1
    )

    assert baseline.fills[0].timestamp == source.bars[1].timestamp
    assert baseline.fills[0].fill_price == Decimal("100")
    assert delayed.fills[0].timestamp == source.bars[2].timestamp
    assert delayed.fills[0].fill_price == Decimal("105")
    assert baseline.fills[1].timestamp == source.bars[4].timestamp
    assert delayed.fills[1].timestamp == source.bars[5].timestamp

    final_signal = FixedSignals(
        (Signal(source.bars[-2].timestamp, SignalAction.LONG),)
    )
    end_delayed = BacktestEngine().run(
        source, final_signal, configuration, execution_delay_bars=1
    )
    assert end_delayed.fills == ()
    assert end_delayed.unexecuted_signals == final_signal.signals


def test_parameter_perturbation_is_transient() -> None:
    original = version()
    scenario = StressScenario(
        "STRESS-PARAMETERS-A",
        "Explicit parameter perturbation",
        StressType.PARAMETER_PERTURBATION,
        {"parameters": {"short_window": 1, "long_window": 3}},
    )
    _, _, parameters, no_effect = apply_stress_scenario(
        scenario,
        BacktestConfiguration(
            Decimal("1000"),
            Decimal("1"),
            ZeroFeeModel(),
            ZeroSlippageModel(),
        ),
        original,
    )
    assert parameters == {"short_window": 1, "long_window": 3}
    assert original.parameters == {"short_window": 2, "long_window": 3}
    assert not no_effect


@pytest.mark.parametrize(
    "scenario",
    [
        lambda: StressScenario(
            "BAD", "Bad", StressType.FEE_MULTIPLIER, {"multiplier": Decimal("1")}
        ),
        lambda: StressScenario(
            "BAD",
            "Bad",
            StressType.EXECUTION_DELAY,
            {"additional_delay_bars": -1},
        ),
    ],
)
def test_invalid_scenarios_fail_before_execution(scenario: object) -> None:
    assert callable(scenario)
    with pytest.raises(ValueError):
        scenario()


def dataset(opens: tuple[str, ...]) -> HistoricalDataset:
    return HistoricalDataset.from_bars(
        market="test",
        instrument="ABC",
        timeframe="daily",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=tuple(
            MarketBar(
                NOW + timedelta(days=index),
                Decimal(value),
                Decimal(value),
                Decimal(value),
                Decimal(value),
                Decimal("1"),
            )
            for index, value in enumerate(opens)
        ),
    )
