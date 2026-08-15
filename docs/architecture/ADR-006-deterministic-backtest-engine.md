# ADR-006: Deterministic backtest engine

- Status: Accepted
- Date: 2026-08-15

## Context

Historical strategy signals must be translated into realistic, reproducible
execution outcomes without introducing future information or mixing strategy,
execution, and accounting responsibilities.

## Decision

Use a deterministic, in-memory, single-asset event-driven engine. Every bar is
processed in this order:

```text
bar open
→ execute the pending LONG/FLAT transition

bar close
→ mark cash and position to market
→ give the strategy only history through this completed bar
→ queue any required transition for the next bar open
```

`Signal`, `Order`, `Fill`, `Position`, and `Trade` remain separate immutable
records. The engine uses deterministic sequence order IDs, `Decimal` monetary
accounting with a fixed local precision, integer position quantities, and no
randomness. Percentage/zero fee models and basis-points/zero slippage models are
explicit and versioned for future `ExperimentRun` lineage.

Position allocation is current cash multiplied by `position_fraction`. The
maximum affordable integer quantity includes buy slippage and fees, so cash never
becomes negative. Spread is not modeled separately; the configured deterministic
slippage is the only price-impact assumption in this version.

A position still open at the end is marked using the final close and is not
liquidated. Its P&L remains unrealized. A final transition with no following bar
is recorded as unexecuted.

## Initial limitations

- one asset;
- LONG/FLAT only;
- market orders only;
- integer quantities;
- no partial fills;
- no leverage or shorting;
- no order-book or separate spread simulation;
- deterministic slippage only;
- no forced end-of-data liquidation;
- no performance metrics or benchmark analytics.

These are intentional MVP constraints.

## Consequences

The engine produces raw orders, fills, completed trades, open-position state, and
an equity curve for later analytics without depending on PostgreSQL or modifying
experiment lineage. Calling the strategy on successive dataset prefixes makes
the no-look-ahead boundary enforceable by construction.
