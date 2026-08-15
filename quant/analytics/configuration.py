from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AnalyticsConfiguration:
    periods_per_year: int
    annual_risk_free_rate: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.periods_per_year, int)
            or isinstance(self.periods_per_year, bool)
            or self.periods_per_year <= 0
        ):
            raise ValueError("periods_per_year must be a positive integer")
        if (
            not isinstance(self.annual_risk_free_rate, Decimal)
            or not self.annual_risk_free_rate.is_finite()
            or self.annual_risk_free_rate <= -1
        ):
            raise ValueError("annual_risk_free_rate must be finite and greater than -1")
