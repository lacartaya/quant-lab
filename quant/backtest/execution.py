from dataclasses import dataclass
from decimal import Context, Decimal, localcontext

from quant.backtest.fees import FeeModel
from quant.backtest.models import Fill, Order, OrderSide
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


def maximum_affordable_quantity(
    *,
    cash: Decimal,
    fraction: Decimal,
    reference_price: Decimal,
    fee_model: FeeModel,
    slippage_model: SlippageModel,
) -> int:
    fill_price = slippage_model.apply(
        side=OrderSide.BUY, reference_price=reference_price
    )
    with localcontext(Context(prec=64)):
        allocation = cash * fraction
        high = int(allocation // fill_price)
        low = 0
        while low < high:
            candidate = (low + high + 1) // 2
            fees = fee_model.calculate(quantity=candidate, price=fill_price)
            if fees < 0:
                raise ValueError("fee model returned a negative fee")
            cost = Decimal(candidate) * fill_price + fees
            if cost <= allocation:
                low = candidate
            else:
                high = candidate - 1
        return low
