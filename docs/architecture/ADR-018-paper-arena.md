# ADR-018: Paper Arena

## Context

Historical validation cannot test behavior on genuinely forward-arriving observations. Before real capital is considered, eligible challengers need forward evidence under simulated execution.

## Decision

Quant Lab introduces persistent paper sessions containing independently capitalized participants. Admission requires an immutable passing `HISTORICAL_TO_PAPER` gate evaluation. Each participant fixes its `StrategyVersion`, gate lineage, initial capital, execution configuration, and `paper-engine-v1` identity.

The initial `replay-provider-v1` feed emits normalized snapshot bars sequentially and exposes no future-bar lookup. A session stores one shared observation stream; all active participants evaluate the same emitted bar. Warm-up bars precede the evaluation boundary and do not contribute paper performance.

Paper execution reuses strategy reconstruction, `BacktestEngine`, cost models, and analytics. For each observation, it deterministically reconstructs the cumulative result from immutable warm-up data plus only emitted observations. Append-only snapshots preserve cumulative orders, fills, trades, equity, metrics, and a material fingerprint. This MVP choice avoids a second simulator and preserves replay/backtest equivalence; a future incremental implementation must retain those guarantees.

Observations are unique by session and timestamp. Identical duplicates are idempotent, conflicting duplicates are integrity errors, and out-of-order bars are rejected. Database uniqueness is the concurrency guard; the local operating model is one worker per session.

Paper evidence uses dedicated records rather than masquerading as historical `ValidationRun` evidence.

## Admission and immutability

A participant references the exact passing gate that admitted it. Later policies do not rewrite that history. Strategy and execution configuration are immutable. Pausing stops evaluation without liquidating; stopping preserves evidence.

## Safety

Paper Arena has no broker port, SDK, credential, real-order endpoint, capital-allocation action, or live-promotion control. Every order and fill is simulated.

## Consequences

Multiple challengers can accumulate comparable forward evidence on a shared feed with independent fake portfolios. Persistent observations and snapshots make replay restart-safe and reproducible. External streaming feeds, broader worker leasing, and every real-money stage are deferred.
