# ADR-020: Backtest visualization and dataset quality

- Status: Accepted
- Date: 2026-08-31

## Decision

Expose a read-only typed projection for one completed ExperimentRun. Immutable
snapshot bars and persisted orders, fills, trades, and strategy/benchmark equity
remain authoritative. Moving-average values and signals were not persisted, so
`moving_average_trend` reconstructs them in the backend from the verified
DatasetSnapshot and exact StrategyVersion. Signal generation shares the same
indicator method; this does not rerun order or portfolio semantics.

Optional UTC `start_at`/`end_at` bounds and a 10,000-bar maximum protect future
intraday use. The dashboard uses pinned `lightweight-charts` 5.0.9 copied from npm
into a local asset; it loads no third-party runtime script.

Quality reports observed range and bars/year, duplicates, ordering, OHLC
validity, and missing values. No exchange calendar is installed, so no complete
market-coverage claim is made. BACKTEST `PASSED` means calculation completion;
the UI says `COMPLETED`, while ValidationGate remains the policy decision.
Expectancy is mean net realized P&L and is currency per trade.

## Consequences

The browser is an evidence viewer, not a backtest engine. Position bands and
display trade IDs are deterministic projections of persisted fills and trade
order. Arbitrary overlays and exchange-calendar completeness remain future work.
