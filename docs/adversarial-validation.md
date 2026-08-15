# Adversarial validation finding API

All thresholds below come from the persisted analyzer configuration. A finding
is cautionary evidence, never an automatic rejection or promotion decision.

## Generalization

| Code | Required evidence | Calculation and threshold | Interpretation / limitation |
|---|---|---|---|
| `OOS_RETURN_DROPOFF` | Backtest and OOS total return | `oos - backtest <= -max_oos_return_drop` | Historical return weakened outside the baseline sample; near-zero relative ratios are intentionally avoided. |
| `OOS_SHARPE_DROPOFF` | Backtest and OOS Sharpe | `oos - backtest <= -max_oos_sharpe_drop` | Risk-adjusted performance weakened; only emitted when both values exist. |
| `OOS_DRAWDOWN_DETERIORATION` | Backtest and OOS maximum drawdown | `backtest_dd - oos_dd >= max_oos_drawdown_worsening` | Held-out drawdown became more negative. |
| `OOS_SIGN_REVERSAL` | Backtest and OOS return | Positive backtest and negative OOS return | Objective return reversal, not proof of overfitting. |
| `OOS_EXPECTANCY_REVERSAL` | Backtest and OOS expectancy | Positive backtest and negative OOS expectancy | Completed-trade expectancy reversed. |
| `OOS_INSUFFICIENT_TRADES` | OOS trade count | Below `min_trade_count_for_interpretation` | Flags limited evidence, not invalidity. |

## Temporal and parameter stability

| Code | Required evidence | Calculation and threshold | Interpretation / limitation |
|---|---|---|---|
| `LOW_PROFITABLE_FOLD_RATIO` | Walk-forward aggregate | Below `min_profitable_fold_ratio` | Few independently capitalized test folds were profitable. |
| `HIGH_RETURN_DISPERSION` | Walk-forward aggregate | Above `max_fold_return_dispersion` | Test-fold returns varied materially. |
| `HIGH_SHARPE_DISPERSION` | Walk-forward aggregate | Above `max_fold_sharpe_dispersion` | Fold Sharpes varied materially. |
| `ISOLATED_PARAMETER_PEAK` | Sensitivity neighborhood | `sharpe_neighbor_delta >= max_neighbor_sharpe_delta` | Baseline Sharpe stands above nearby configured parameters; not proof of overfitting. |
| `LOW_PROFITABLE_PARAMETER_RATIO` | Sensitivity summary | Below `min_profitable_parameter_ratio` | Profitability is uncommon on the tested finite surface. |
| `HIGH_PARAMETER_METRIC_DISPERSION` | Sensitivity summary | Above `max_parameter_sharpe_dispersion` | Candidate Sharpes are unstable across the configured surface. |

## Execution stress

| Code | Required evidence | Calculation and threshold | Interpretation / limitation |
|---|---|---|---|
| `FEE_SENSITIVITY` | Fee scenario | Return delta at or below `-max_stress_return_drop` | Return depends on baseline fee assumptions. |
| `SLIPPAGE_SENSITIVITY` | Slippage scenario | Same delta rule | Return depends on baseline slippage assumptions. |
| `ADVERSE_FILL_SENSITIVITY` | Adverse-price scenario | Same delta rule | Return deteriorates with worse fills. |
| `EXECUTION_TIMING_FRAGILITY` | Delay scenario | Same delta rule | Return depends on precise execution timing. |
| `STRESS_RETURN_SIGN_REVERSAL` | Any stress scenario | Positive baseline and negative stressed return | The scenario reverses return sign. |
| `STRESS_DRAWDOWN_EXPANSION` | Any stress scenario | Worsening at least `max_stress_drawdown_worsening` | Drawdown becomes materially more negative. |

## Sequence risk

| Code | Required evidence | Calculation and threshold | Interpretation / limitation |
|---|---|---|---|
| `HIGH_BOOTSTRAP_LOSS_FREQUENCY` | Monte Carlo distribution | Empirical loss frequency at least `max_bootstrap_loss_frequency` | Conditional bootstrap frequency, not a future probability. |
| `LARGE_ADVERSE_DRAWDOWN` | Drawdown percentiles | Most adverse configured percentile at or below `max_adverse_bootstrap_drawdown` | Sampled sequences contain deep drawdowns. |
| `LONG_LOSS_STREAK_RISK` | Loss-streak percentiles | Largest configured percentile at least `max_bootstrap_losing_streak` | Sampled sequences contain long losing runs. |
| `HISTORICAL_RESULT_HIGH_RELATIVE_TO_BOOTSTRAP` | Historical percentile position | At least `max_historical_return_percentile` | Realized history lies high in the empirical distribution; it does not quantify luck. |

## Concentration, sample size, and benchmark

| Code | Required evidence | Calculation and threshold | Interpretation / limitation |
|---|---|---|---|
| `TOP_TRADE_CONCENTRATION` | Positive completed trades | Largest positive net P&L / gross positive P&L | Winning profit depends strongly on one trade. |
| `TOP_3_TRADES_CONCENTRATION` | At least three winning trades | Top three positive net P&Ls / gross positive P&L | Winning profit depends strongly on three trades. |
| `LOW_COMPLETED_TRADE_COUNT` | Backtest MetricSet | Below `min_trade_count_for_interpretation` | Small sample warning only. |
| `BENCHMARK_DOMINANCE` | Strategy and Buy & Hold return, drawdown, Sharpe | Benchmark is no worse on all three | Not emitted when the strategy has the better drawdown, even if benchmark return is higher. |

## Validation coverage

For every absent source type the analyzer emits `<TYPE>_NOT_AVAILABLE` with INFO
severity and records `coverage[type] = false`. Missing evidence is not evidence
of robustness and is not treated as a failed validation.
