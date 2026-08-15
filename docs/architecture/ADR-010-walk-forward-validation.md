# ADR-010: Walk-forward validation

- Status: Accepted
- Date: 2026-08-15

## Context

A full-history backtest or one held-out period can depend heavily on a particular
market regime or boundary choice. Quant Lab needs chronological evidence across
several future periods without parameter selection or future-data leakage.

## Decision

Evaluate one fixed, persisted `StrategyVersion` through deterministic sequential
test folds. QL-010 uses explicit bar-count `training_window`, `test_window`, and
`step` values rather than exchange-calendar arithmetic. Generated folds persist
their resolved UTC timestamps and source-bar indexes.

Both modes are supported:

- `EXPANDING` keeps the first training bar fixed and grows history each fold.
- `ROLLING` advances a fixed-size history window with each fold.

`step` must be at least `test_window`, so test bars do not overlap. Only complete
folds are emitted; an incomplete final period is skipped, and zero complete folds
is an error.

Training bars are historical signal context, not fitted-model evidence. For each
fold the portfolio starts again with persisted initial capital. A signal at the
final training close may execute at the first test open, preserving the QL-006
next-bar rule. Equity, trades, and metrics before `test_start` are excluded. Each
fold is truncated at its own `test_end`, so later data cannot affect earlier
decisions.

Every fold also runs Buy & Hold over the same test interval with identical
capital, sizing, fees, and slippage. Fold evidence records fixed strategy
identity, boundaries, execution records, strategy and benchmark metrics, and
excess total return. Aggregate evidence reports counts, ratios, means, medians,
worst drawdown, and population dispersion; it defines no quality threshold.

Walk-forward evidence is stored as JSON on a distinct
`ValidationType.WALK_FORWARD` record. `PASSED` means the calculation completed,
not that the strategy met an investment threshold. The record includes
`walk-forward-v1`, dataset checksum, execution and analytics lineage, warm-up and
independent-capital conventions, folds, aggregate evidence, and a canonical
SHA-256 fingerprint. Reproduction verifies the dataset, reconstructs stored
versions and parameters, reruns every fold, and compares material evidence.

No database schema change is required because ValidationRun JSONB configuration
already supports versioned validation evidence.

## Consequences

The platform can observe temporal stability and regime dependence more clearly
than with one boundary. Walk-forward evidence does not prove future profitability
and must later be combined with sensitivity, stress, and other robustness
evidence. No optimization or chained model selection occurs in QL-010.
