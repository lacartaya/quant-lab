"""Deterministic analytics over completed backtest results."""

from quant.analytics.benchmark import (
    BenchmarkResult,
    PerformanceComparison,
    buy_and_hold_benchmark,
    compare_to_benchmark,
)
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
from quant.analytics.service import METRICS_VERSION, analyze_backtest
from quant.analytics.trade_metrics import trade_statistics

__all__ = [
    "METRICS_VERSION",
    "AnalyticsConfiguration",
    "BenchmarkResult",
    "PerformanceComparison",
    "analyze_backtest",
    "annualized_volatility",
    "buy_and_hold_benchmark",
    "calmar_ratio",
    "compare_to_benchmark",
    "compound_annual_growth_rate",
    "maximum_drawdown",
    "periodic_returns",
    "sharpe_ratio",
    "sortino_ratio",
    "total_return",
    "trade_statistics",
]
