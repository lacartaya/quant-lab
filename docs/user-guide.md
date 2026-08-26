# Quant Lab user guide

Quant Lab is a research notebook with strict memory. It records an investment
idea, the data used to test it, every validation attempt, and simulated paper
evidence. It does not promise profit and cannot trade real money.

## Basic terms

- **Asset/instrument**: what is observed, such as the SPY exchange-traded fund.
- **Timeframe**: the duration represented by one price bar, such as one day.
- **OHLCV**: open, high, low, close, and traded volume for one bar.
- **Historical data**: observations already recorded. Alpaca IEX or local CSV can
  supply them.
- **DatasetSnapshot**: an immutable copy of normalized bars. Its checksum proves
  which exact data was used.
- **Hypothesis**: a precise research idea and the conditions that could disprove
  it.
- **Strategy/StrategyVersion**: fixed trading logic and fixed parameters.
- **Experiment**: one strategy version tested on one dataset snapshot.
- **Backtest**: simulated execution over stored historical bars.
- **Buy & Hold benchmark**: context showing what passive ownership did over the
  same period; it is not an automatic winner.
- **OOS**: an out-of-sample period held away from initial research.
- **Walk-forward**: repeated time-ordered train/test folds.
- **Parameter sensitivity**: checks whether nearby parameters behave similarly.
- **Stress testing**: makes costs, fills, timing, or assumptions worse.
- **Monte Carlo/bootstrap**: resamples observed trade outcomes to show sequence
  risk; it is not a future-price forecast.
- **Adversarial validation**: deterministic findings that try to surface weak or
  misleading evidence.
- **Validation gate**: an explicit versioned policy. PASS means only that its
  rules were met, not that a strategy is safe or profitable.
- **Research memory**: searchable successful and rejected work. REJECTED applies
  only to its tested domain, not everywhere forever.
- **Paper trading**: fake-capital trading. Alpaca Paper is an external simulator;
  Paper Arena is Quant Lab's own simulator.

## Dashboard workflow

Open `/dashboard/`. The overview shows research counts, experiments, datasets,
Paper Arena, and research memory.

1. In **Market Data / Datasets**, import an Alpaca daily symbol or inspect an
   existing snapshot. The provider, IEX feed, range, storage identity, and
   checksum remain visible.
2. Use **Prior-art check** before repeating an idea. Exact rejected prior art can
   block trivial repetition; similar work is evidence, not an automatic ban.
3. Open an experiment to inspect strategy, dataset lineage, metrics, Buy & Hold,
   every separate validation, adversarial findings, and gate rules.
4. Open **Paper Arena** to compare gate-admitted versions on independent fake
   portfolios. No single “winner” is selected.
5. Open **Alpaca Paper Trading** to verify the simulated account and inspect or
   deliberately submit paper orders. Confirmations do not make an order real;
   they prevent accidental simulated writes.

The dashboard never calculates authoritative metrics and never calls Alpaca
directly. For workflows not exposed as dashboard writes, use OpenAPI `/docs`,
the curl guide, or Bruno. Creation of complete research/validation pipelines is
not yet exposed as a single public API workflow; persisted results remain fully
inspectable.
