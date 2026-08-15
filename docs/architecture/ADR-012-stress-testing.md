# ADR-012: Stress testing

- Status: Accepted
- Date: 2026-08-15

## Context

Historical results may rely on optimistic execution, cost, timing, or strategy
assumptions. Baseline backtests alone do not show how quickly apparent behavior
deteriorates when those assumptions become less favorable.

## Decision

Introduce deterministic, explicitly configured adverse scenarios that modify one
controlled assumption at a time. QL-012 supports:

- percentage-fee multipliers;
- basis-point slippage multipliers;
- additional adverse execution basis points;
- fixed additional execution-delay bars;
- explicit transient Moving Average parameter perturbations.

The baseline is reconstructed from the completed ExperimentRun and uses its exact
StrategyVersion, DatasetSnapshot, checksum, BacktestConfiguration, engine, costs,
and analytics configuration. Unless parameter perturbation is the named stress,
strategy parameters remain unchanged. Parameter candidates never mutate or
create StrategyVersions.

Fee and slippage multipliers retain the original model type. Multiplying a zero
cost remains zero and is recorded as `no_effect`, rather than presented as useful
cost stress. Adverse-price stress composes additional basis points into the
existing directional slippage model, so BUY fills rise and SELL fills fall.

Execution delay applies equally to entries and exits. The baseline signal-close
to-next-open rule remains delay zero; `additional_delay_bars = 1` executes one
open later. Pending transitions retain their countdown while the desired state is
unchanged and are cancelled if the strategy returns to the current portfolio
state. A transition beyond available data remains unexecuted; no bar or fill is
fabricated.

Each scenario stores material backtest evidence, MetricSet, effective
configuration, benchmark context, and objective baseline deltas. Retained-return
and retained-Sharpe ratios are only defined for positive baselines. Aggregate
evidence reports profitability, medians, worst return/Sharpe/drawdown, baseline
outperformance count, and worst scenario identities. It defines no score,
promotion rule, or rejection threshold.

The baseline benchmark is reused for timing and parameter stresses. Cost and
adverse-price scenarios rerun Buy & Hold because those execution assumptions are
shared with the benchmark.

Stress evidence is persisted as `ValidationType.STRESS` in existing ValidationRun
JSONB with version `stress-validation-v1`. It includes every configured scenario,
the full-history research range, execution lineage, results, aggregate evidence,
and a canonical SHA-256 fingerprint. Reproduction checksum-verifies the snapshot
and reruns baseline and scenarios solely from stored lineage.

As with QL-011, only `FULL_HISTORY_RESEARCH` is currently enforceable because the
repository has no QL-009 OOS service or persisted in-sample boundary. Evidence is
therefore marked as contaminating future OOS interpretation.

## Important principle

Stress testing attempts to invalidate apparently strong results under controlled
adverse assumptions. It does not seek better parameters and does not
automatically promote or reject a strategy.

## Limitations

QL-012 does not simulate partial fills, broker outages, order-book liquidity,
market impact, portfolio correlation shocks, multi-asset behavior, random data
loss, or Monte Carlo outcomes. Missing-data and skipped-execution scenarios are
also deferred rather than introducing a new synthetic-data policy.

## Consequences

Quant Lab can measure whether historical behavior deteriorates materially under
less favorable deterministic assumptions while retaining complete scenario
lineage. Survival is robustness evidence, not proof of future profitability.
