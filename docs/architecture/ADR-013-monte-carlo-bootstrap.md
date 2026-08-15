# ADR-013: Monte Carlo bootstrap robustness

- Status: Accepted
- Date: 2026-08-15

## Context

One realized historical trade sequence may understate or overstate a strategy's
exposure to sequence risk, losing streaks, and drawdowns. Quant Lab needs a
reproducible distribution of alternate paths without pretending to forecast
market prices.

## Decision

Use an empirical trade-return bootstrap over the completed trades preserved in a
specific completed ExperimentRun's canonical BACKTEST evidence. For each trade,
the normalized observation is:

```text
net realized P&L / (entry price × quantity + entry fees)
```

`Trade.realized_pnl` is already net of entry and exit fees, so costs are not
subtracted again. The denominator is the exact entry capital recorded by QL-006.
This makes the return basis reconstructible without inventing portfolio exposure.
The bootstrap then compounds each sampled trade return against the whole
simulated equity. This is a deliberately simple sequence-risk model; it does not
recreate the original strategy's varying cash allocation between trades.

Each simulation samples the original number of trade returns with replacement.
It starts from the ExperimentRun's persisted initial cash and retains only a
compact path summary: final/minimum equity, total return, maximum drawdown, and
maximum consecutive losing trades. Full simulated curves are transient and are
not persisted.

Every configuration explicitly records the simulation count, seed, empirical
percentiles, sampling method, and optional drawdown and ruin thresholds. A local
`random.Random(seed)` instance isolates the simulation from global RNG state.
The implementation caps runs at 100,000 simulations and requires at least two
completed trades. Two is a technical minimum, not a claim of statistical
sufficiency.

Percentiles use deterministic linear interpolation at position
`(sample_count - 1) × percentile`. Maximum drawdown follows the negative running
peak convention in `docs/metrics.md`. A zero return ends a losing streak.
Frequencies are named empirical frequencies because they are conditional on the
historical sample and bootstrap assumptions.

Monte Carlo evidence is stored as `ValidationType.MONTE_CARLO` in the existing
ValidationRun JSONB. Version `monte-carlo-v1`, the ordered observations and their
SHA-256 fingerprint, source run/validation identity, dataset checksum, compact
path summaries, distributions, and result fingerprint are persisted. Before
execution or reproduction, the immutable DatasetSnapshot is loaded so its file
checksum and metadata are verified. Reproduction uses only persisted source
evidence and configuration.

## Interpretation

Bootstrap results describe outcome dispersion conditional on observed trades,
their empirical distribution, the sample-with-replacement assumption, and the
chosen compounding model. They are not confidence guarantees, price forecasts,
or proof of future profitability. The initial source scope is one BACKTEST; OOS,
walk-forward stitching, and mixed validation samples are not silently combined.

## Consequences

Quant Lab can inspect empirical final-equity, return, drawdown, and loss-streak
distributions while reproducing exact seeded results after restart. Trade
dependence and regime clustering are not preserved by the standard bootstrap.
Block bootstrap, periodic-return bootstrap, representative full paths,
portfolio-level correlation simulation, and forecasting models are deferred.
