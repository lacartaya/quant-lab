# Performance metric definitions

Quant Lab analytics formula set `metrics-v1` uses the following conventions.
Monetary backtest values are `Decimal`; analytics explicitly converts equity and
net trade P&L to `float` where roots, powers, means, or standard deviations are
required.

- **Periodic return:** `equity[t] / equity[t-1] - 1`. Initial cash is prepended
  to the equity curve as initial equity. A zero or negative prior equity is
  invalid.
- **Total return:** `final equity / initial equity - 1`. Final equity includes an
  open position marked at the final close.
- **CAGR:** `(final equity / initial equity) ** (periods_per_year / period_count)
  - 1`. Period count is the number of portfolio returns. With no periods it is
  undefined (`None`).
- **Maximum drawdown:** the most negative value of `equity / running peak - 1`.
- **Volatility:** sample standard deviation of periodic returns, multiplied by
  `sqrt(periods_per_year)`. Fewer than two returns is undefined.
- **Sharpe:** mean periodic excess return divided by its sample standard
  deviation, annualized by `sqrt(periods_per_year)`. Periodic risk-free return is
  `(1 + annual_rate) ** (1 / periods_per_year) - 1`. Zero deviation is undefined.
- **Sortino:** mean periodic excess return divided by downside deviation and
  annualized by `sqrt(periods_per_year)`. Downside deviation is the root mean
  square of `min(excess_return, 0)` across all periods. No downside is undefined.
- **Calmar:** CAGR divided by the absolute maximum drawdown. Zero drawdown is
  undefined.
- **Trade count:** number of completed round-trip `Trade` records. Open positions
  do not count.
- **Win rate:** positive-net-P&L trades divided by all completed trades.
  Breakeven trades remain in the denominator but are not wins. No trades is
  undefined.
- **Profit factor:** gross positive net trade P&L divided by absolute gross
  negative net trade P&L. With no losing trades it is undefined rather than
  infinity.
- **Expectancy:** average completed `Trade.realized_pnl`. QL-006 P&L is already
  net of entry and exit fees, so analytics does not subtract costs again.

Undefined metrics are `None`, never artificial zero or infinity. Annualization
and annual risk-free rate are explicit inputs; analytics does not infer exchange
calendars or fetch rates.
