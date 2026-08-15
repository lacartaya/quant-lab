from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from typing import Protocol

from quant.backtest.models import OrderSide


class SlippageModel(Protocol):
    @property
    def version(self) -> str: ...

    def apply(self, *, side: OrderSide, reference_price: Decimal) -> Decimal: ...


@dataclass(frozen=True, slots=True)
class ZeroSlippageModel:
    version = "zero-v1"

    def apply(self, *, side: OrderSide, reference_price: Decimal) -> Decimal:
        if reference_price <= 0:
            raise ValueError("reference_price must be positive")
        return reference_price


@dataclass(frozen=True, slots=True)
class BasisPointsSlippageModel:
    basis_points: Decimal

    def __post_init__(self) -> None:
        if (
            not self.basis_points.is_finite()
            or self.basis_points < 0
            or self.basis_points >= Decimal(10_000)
        ):
            raise ValueError("basis_points must be between 0 and 10000")

    @property
    def version(self) -> str:
        return f"basis-points-v1:{self.basis_points.normalize()}"

    def apply(self, *, side: OrderSide, reference_price: Decimal) -> Decimal:
        if reference_price <= 0:
            raise ValueError("reference_price must be positive")
        direction = Decimal(1) if side is OrderSide.BUY else Decimal(-1)
        with localcontext(Context(prec=64)):
            return reference_price * (
                Decimal(1) + direction * self.basis_points / Decimal(10_000)
            )
