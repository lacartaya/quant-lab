# ADR-007: Performance analytics

- Status: Accepted
- Date: 2026-08-15

## Context

Backtest results require deterministic quantitative evaluation before they can
support later validation or comparison. Metric calculation must not leak into
strategy behavior, execution simulation, portfolio accounting, or persistence.

## Decision

Keep analytics downstream of `BacktestResult`. Use the equity curve, preceded by
initial capital, for portfolio return and risk metrics. Use completed `Trade`
records for trade metrics. Annualization periods and annual risk-free rate are
explicit configuration values.

Formula set `metrics-v1` uses sample standard deviation for volatility and
Sharpe, and root-mean-square negative excess returns across all observations for
Sortino downside deviation. Statistical values that are mathematically undefined
are represented by `None`, not zero or infinity. Exact definitions are maintained
in `docs/metrics.md`.

Buy & Hold is the first and only benchmark. It buys at the first bar open using
the same initial cash, position fraction, integer sizing, fees, and slippage as
the strategy simulation, then marks the open position at the final close without
forcing a sale. Comparison reports both metric sets and excess total return; it
does not rank, score, validate, or promote a strategy.

Monetary accounting remains `Decimal`. Conversion to `float` occurs explicitly
at the analytics boundary because standard-library statistical roots and powers
operate in floating point.

## Consequences

Metrics remain reproducible and independently testable, while execution remains
free of analytics concerns. Alternative conventions or formula changes must use
a new documented metric version in the future.
