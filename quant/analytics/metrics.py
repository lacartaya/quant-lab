import math
import statistics
from collections.abc import Sequence


def periodic_returns(equities: Sequence[float]) -> tuple[float, ...]:
    if len(equities) < 2:
        return ()
    if any(not math.isfinite(value) or value <= 0 for value in equities[:-1]):
        raise ValueError("prior equity values must be positive and finite")
    if not math.isfinite(equities[-1]) or equities[-1] < 0:
        raise ValueError("final equity must be non-negative and finite")
    return tuple(
        current / previous - 1
        for previous, current in zip(equities, equities[1:], strict=False)
    )


def total_return(initial_equity: float, final_equity: float) -> float:
    if not math.isfinite(initial_equity) or initial_equity <= 0:
        raise ValueError("initial equity must be positive and finite")
    if not math.isfinite(final_equity) or final_equity < 0:
        raise ValueError("final equity must be non-negative and finite")
    return final_equity / initial_equity - 1


def compound_annual_growth_rate(
    initial_equity: float,
    final_equity: float,
    period_count: int,
    periods_per_year: int,
) -> float | None:
    if initial_equity <= 0 or final_equity < 0:
        raise ValueError("equities must have positive start and non-negative end")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    if period_count <= 0:
        return None
    ratio = final_equity / initial_equity
    return math.pow(ratio, periods_per_year / period_count) - 1


def maximum_drawdown(equities: Sequence[float]) -> float:
    if not equities:
        raise ValueError("equity values cannot be empty")
    if equities[0] <= 0 or any(
        not math.isfinite(value) or value < 0 for value in equities
    ):
        raise ValueError(
            "equity values must have positive start and non-negative values"
        )
    peak = equities[0]
    lowest = 0.0
    for equity in equities:
        peak = max(peak, equity)
        lowest = min(lowest, equity / peak - 1)
    return lowest


def annualized_volatility(
    returns: Sequence[float], periods_per_year: int
) -> float | None:
    if len(returns) < 2:
        return None
    return statistics.stdev(returns) * math.sqrt(periods_per_year)


def periodic_risk_free_rate(annual_rate: float, periods_per_year: int) -> float:
    return math.pow(1 + annual_rate, 1 / periods_per_year) - 1


def sharpe_ratio(
    returns: Sequence[float], periods_per_year: int, annual_risk_free_rate: float
) -> float | None:
    if len(returns) < 2:
        return None
    target = periodic_risk_free_rate(annual_risk_free_rate, periods_per_year)
    excess = [value - target for value in returns]
    deviation = statistics.stdev(excess)
    if deviation == 0:
        return None
    return statistics.mean(excess) / deviation * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: Sequence[float], periods_per_year: int, annual_risk_free_rate: float
) -> float | None:
    if not returns:
        return None
    target = periodic_risk_free_rate(annual_risk_free_rate, periods_per_year)
    excess = [value - target for value in returns]
    downside = math.sqrt(sum(min(value, 0.0) ** 2 for value in excess) / len(excess))
    if downside == 0:
        return None
    return statistics.mean(excess) / downside * math.sqrt(periods_per_year)


def calmar_ratio(cagr: float | None, max_drawdown: float) -> float | None:
    if cagr is None or max_drawdown == 0:
        return None
    return cagr / abs(max_drawdown)
