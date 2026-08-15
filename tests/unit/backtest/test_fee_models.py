from decimal import Decimal

import pytest

from quant.backtest import PercentageFeeModel, ZeroFeeModel


def test_zero_fee_model() -> None:
    assert ZeroFeeModel().calculate(quantity=10, price=Decimal("100")) == Decimal(0)


def test_percentage_fee_golden_example() -> None:
    model = PercentageFeeModel(Decimal("0.01"))
    assert model.calculate(quantity=10, price=Decimal("100")) == Decimal("10")


def test_negative_fee_rate_is_rejected() -> None:
    with pytest.raises(ValueError, match="fee rate"):
        PercentageFeeModel(Decimal("-0.01"))
