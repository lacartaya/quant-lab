from quant.analytics.configuration import AnalyticsConfiguration
from quant.analytics.metrics import (
    annualized_volatility,
    calmar_ratio,
    compound_annual_growth_rate,
    maximum_drawdown,
    periodic_returns,
    sharpe_ratio,
    sortino_ratio,
    total_return,
)
from quant.analytics.trade_metrics import trade_statistics
from quant.backtest import BacktestResult
from quant.domain import MetricSet

METRICS_VERSION = "metrics-v1"


def analyze_backtest(
    result: BacktestResult, configuration: AnalyticsConfiguration
) -> MetricSet:
    if not result.equity_curve:
        raise ValueError("backtest equity curve cannot be empty")
    equities = (float(result.initial_cash),) + tuple(
        float(point.equity) for point in result.equity_curve
    )
    returns = periodic_returns(equities)
    total = total_return(equities[0], equities[-1])
    cagr = compound_annual_growth_rate(
        equities[0], equities[-1], len(returns), configuration.periods_per_year
    )
    drawdown = maximum_drawdown(equities)
    risk_free_rate = float(configuration.annual_risk_free_rate)
    profit_factor, win_rate, expectancy, trade_count = trade_statistics(result.trades)
    return MetricSet(
        total_return=total,
        cagr=cagr,
        max_drawdown=drawdown,
        volatility=annualized_volatility(returns, configuration.periods_per_year),
        sharpe=sharpe_ratio(
            returns, configuration.periods_per_year, risk_free_rate
        ),
        sortino=sortino_ratio(
            returns, configuration.periods_per_year, risk_free_rate
        ),
        calmar=calmar_ratio(cagr, drawdown),
        profit_factor=profit_factor,
        win_rate=win_rate,
        expectancy=expectancy,
        trade_count=trade_count,
    )
