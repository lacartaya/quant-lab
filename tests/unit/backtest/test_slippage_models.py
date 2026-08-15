from decimal import Decimal

import pytest

from quant.backtest import (
    BasisPointsSlippageModel,
    OrderSide,
    ZeroSlippageModel,
)


def test_zero_slippage_model() -> None:
    assert ZeroSlippageModel().apply(
        side=OrderSide.BUY, reference_price=Decimal("100")
    ) == Decimal("100")


def test_ten_basis_points_golden_example() -> None:
    model = BasisPointsSlippageModel(Decimal("10"))
    assert model.apply(
        side=OrderSide.BUY, reference_price=Decimal("100")
    ) == Decimal("100.10")
    assert model.apply(
        side=OrderSide.SELL, reference_price=Decimal("100")
    ) == Decimal("99.90")


@pytest.mark.parametrize("basis_points", [Decimal("-1"), Decimal("10000")])
def test_invalid_slippage_is_rejected(basis_points: Decimal) -> None:
    with pytest.raises(ValueError, match="basis_points"):
        BasisPointsSlippageModel(basis_points)
