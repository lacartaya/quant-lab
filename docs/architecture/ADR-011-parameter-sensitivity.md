# ADR-011: Parameter sensitivity

- Status: Accepted
- Date: 2026-08-15

## Context

Historically attractive strategies may owe their apparent performance to one
narrow parameter combination. A single optimum does not show whether nearby
implementations behave consistently, and selecting it automatically would turn
robustness analysis into optimization.

## Decision

Evaluate deterministic finite parameter grids around an existing, immutable
`StrategyVersion`. QL-011 initially supports the Moving Average Trend algorithm's
integer `short_window` and `long_window` parameters.

Parameter names are sorted and each configured axis retains its supplied value
order. The Cartesian-product size is checked against `maximum_combinations`
before execution and is never truncated. Each candidate is validated by
`MovingAverageParameters`; invalid combinations are excluded and counted. The
baseline is identified once or appended explicitly when absent, subject to the
same maximum guard. Candidate IDs are stable sequential values.

Candidates are transient executable configurations, not StrategyVersions. Only
their specified parameters vary. Dataset snapshot, checksum, initial capital,
position fraction, engine, fee and slippage configuration, analytics version,
and risk-free-rate assumptions remain fixed. Buy & Hold is calculated once for
the shared evaluation period.

The surface stores every valid candidate's parameters, relative parameter
distance, MetricSet, and material backtest evidence. Summaries report requested,
executed, invalid, and profitable counts; medians; population dispersion;
baseline-relative ratios; and the Sharpe range and median of the baseline's
one-axis adjacent configured neighbors. `sharpe_neighbor_delta` is descriptive
evidence, not an overfitting score or rejection rule. No winner is selected.

Parameter-sensitivity evidence is persisted as a distinct
`ValidationType.PARAMETER_SENSITIVITY` record with version
`parameter-sensitivity-v1`. JSONB stores the complete grid, candidate ordering,
lineage, benchmark, summaries, and canonical SHA-256 fingerprint. Reproduction
checksum-verifies the snapshot and regenerates the surface solely from persisted
configuration. The database validation-type check constraint is extended through
Alembic migration `20260815_0004`.

## OOS principle

Sensitivity should normally use an explicit research/in-sample region so held-out
OOS evidence remains unseen. This repository does not currently contain the
QL-009 OOS execution layer or an enforceable in-sample boundary. QL-011 therefore
supports only the explicitly named `FULL_HISTORY_RESEARCH` scope and persists
`contaminates_future_oos_interpretation = true`. Any future challenger influenced
by this surface must not treat the evaluated period as unseen OOS evidence.

## Consequences

Quant Lab can distinguish broad historical stability from an isolated peak and
retains the number and content of attempted combinations. Mechanical candidates
do not pollute StrategyVersion lineage. A promising candidate must become a new
hypothesis and intentional StrategyVersion and then repeat the full validation
lifecycle. No automatic selection, promotion, or parameter mutation occurs.
