from dataclasses import dataclass

from quant.backtest.fees import FeeModel
from quant.backtest.models import Fill, Order
from quant.backtest.slippage import SlippageModel


@dataclass(frozen=True, slots=True)
class ExecutionSimulator:
    fee_model: FeeModel
    slippage_model: SlippageModel

    def execute(self, order: Order) -> Fill:
        fill_price = self.slippage_model.apply(
            side=order.side, reference_price=order.reference_price
        )
        fees = self.fee_model.calculate(quantity=order.quantity, price=fill_price)
        return Fill(
            order_id=order.id,
            timestamp=order.timestamp,
            side=order.side,
            quantity=order.quantity,
            reference_price=order.reference_price,
            fill_price=fill_price,
            fees=fees,
            slippage=abs(fill_price - order.reference_price),
        )
