# Paper Arena

Paper Arena consumes bars one at a time and simulates trading with fake capital. It never submits broker orders.

## Sessions and participants

A session identifies a market, instrument, timeframe, immutable feed lineage, evaluation boundary, provider version, and status. Participants share its observations while owning independent portfolios. Each fixes its strategy version, passing admission gate, starting capital, costs, and paper-engine version.

Admission requires `PASS` from the exact `HISTORICAL_TO_PAPER` gate evaluation. A newer evaluation never rewrites existing admission lineage.

## Replay and timing

`replay-provider-v1` emits eligible bars in timestamp order and has no future-bar lookup. Evaluation receives warm-up bars and only observations emitted so far. A close signal at bar `t` fills no earlier than the next emitted bar's open, matching historical timing. Warm-up performance is excluded and data gaps are not filled.

An `alpaca_iex` session may instead poll the latest external one-minute IEX bar
through `AlpacaLiveMarketDataProvider`. It requires a compatible one-minute
warm-up DatasetSnapshot. This changes the observation source only: fills remain
Quant Lab internal simulations and strategy orders are not routed to Alpaca.

## Persistence and recovery

PostgreSQL stores sessions, participants, shared observations, and append-only cumulative snapshots. Snapshots contain simulated orders, fills, trades, equity, metrics, and deterministic fingerprints.

- An identical repeated bar is ignored.
- A repeated timestamp with different OHLCV is an integrity conflict.
- Older observations are rejected rather than revising history.
- Failed transactions do not mark an observation processed.
- Restart advances from the last timestamp without resetting capital or duplicating evidence.

Run one processor per session in the local MVP; database uniqueness protects observation and snapshot identity if processors race.

## Metrics and operations

Metrics reuse deterministic analytics and retain `None` when undefined. Comparisons report multidimensional evidence without selecting a winner. Pausing preserves positions and stops new evaluation. Stopping retains every artifact.

## Safety boundary

Alpaca Paper brokerage is a separate external simulator and is always labeled
PAPER. There is no live-money broker adapter, live-order route, real capital,
production promotion, or manual metric/gate override. Historical eligibility
permits simulated paper admission only.
