# ADR-005: Strategy execution model

- Status: Accepted
- Date: 2026-08-15

## Context

Quant Lab needs deterministic strategy implementations that remain separate from
market-data providers, execution, and infrastructure. The existing `Strategy`
domain entity represents a logical research identity; it is not executable
behavior.

## Decision

Introduce `ExecutableStrategy` as the runtime signal-generation contract and keep
the existing `Strategy` and `StrategyVersion` lineage concepts unchanged. The
first implementation is `MovingAverageTrendStrategy`, identified by the stable
key `moving_average_trend`.

The strategy:

- consumes an explicitly supplied `HistoricalDataset`;
- reads normalized closing prices exactly as supplied, including the dataset's
  explicit adjustment policy;
- uses typed, immutable short- and long-window parameters;
- generates deterministic `LONG` or `FLAT` intended-state signals;
- does not execute trades, size positions, or access external systems.

No signal is produced during warm-up. Once the long window is available, one
state signal is emitted for every eligible bar. State-on-every-bar signals were
chosen over transition-only events so a future backtest engine can observe the
complete intended state without reconstructing it from earlier history.

## Signal timing

Each signal timestamp is the timestamp of the completed bar whose close made the
moving averages available. A signal therefore becomes known only at that bar's
close. This does not imply execution at the same close. QL-006 must explicitly
choose a later executable point, such as the next bar.

The algorithm processes bars chronologically and computes each signal only from
the current and preceding closes. It never reads future bars for an earlier
signal.

## Baseline parameters

The default configuration uses a 50-bar short window and a 200-bar long window.
This is a simple established trend-following demonstration, not an optimized
choice, profitability claim, validation result, or promotion threshold.

## Consequences

A future backtest engine can consume explicit strategy state without embedding
strategy logic inside the execution simulator. `StrategyVersion.parameters` can
record the typed parameter object's serialized dictionary without changing the
current persistence schema.
