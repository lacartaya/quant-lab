from dataclasses import dataclass
from decimal import Decimal

from quant.backtest.fees import FeeModel
from quant.backtest.slippage import SlippageModel


@dataclass(frozen=True, slots=True)
class BacktestConfiguration:
    initial_cash: Decimal
    position_fraction: Decimal
    fee_model: FeeModel
    slippage_model: SlippageModel

    def __post_init__(self) -> None:
        if not self.initial_cash.is_finite() or self.initial_cash <= 0:
            raise ValueError("initial_cash must be a positive finite Decimal")
        if (
            not self.position_fraction.is_finite()
            or self.position_fraction <= 0
            or self.position_fraction > 1
        ):
            raise ValueError("position_fraction must be greater than 0 and at most 1")
