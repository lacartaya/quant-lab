from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from typing import Protocol


class FeeModel(Protocol):
    @property
    def version(self) -> str: ...

    def calculate(self, *, quantity: int, price: Decimal) -> Decimal: ...


@dataclass(frozen=True, slots=True)
class ZeroFeeModel:
    version = "zero-v1"

    def calculate(self, *, quantity: int, price: Decimal) -> Decimal:
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be positive")
        return Decimal(0)


@dataclass(frozen=True, slots=True)
class PercentageFeeModel:
    rate: Decimal

    def __post_init__(self) -> None:
        if not self.rate.is_finite() or self.rate < 0:
            raise ValueError("fee rate must be a non-negative finite Decimal")

    @property
    def version(self) -> str:
        return f"percentage-v1:{self.rate.normalize()}"

    def calculate(self, *, quantity: int, price: Decimal) -> Decimal:
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be positive")
        with localcontext(Context(prec=64)):
            return Decimal(quantity) * price * self.rate
