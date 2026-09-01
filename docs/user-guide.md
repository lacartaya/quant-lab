# Quant Lab user guide

## Your First Real Research Experiment — SPY 50/200

Open **New Research** in the dashboard. Choose an existing SPY `1Day` dataset,
create the supplied hypothesis, create the `moving_average_trend` StrategyVersion
with short window 50 and long window 200, bind those records into an experiment,
and press **Run experiment**. Each form can copy the equivalent curl request.

The result page shows the immutable lineage, execution assumptions, metrics, Buy
& Hold comparison, and BACKTEST validation. A good-looking result is evidence,
not a promise and not permission to trade real money. See
[the exact walkthrough](first-real-research-run.md) for the curl sequence.

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
- **Paper eligible**: the exact historical candidate has a PASS gate and intact
  lineage; no human approval has been recorded yet.
- **Paper approved**: a local operator explicitly authorized forward-only fake-
  capital observation. No session starts automatically.
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
4. Review **Paper Promotion** after a Gate PASS and explicitly approve the exact
   immutable StrategyVersion. Historical validation does not guarantee future
   performance.
5. Open **Paper Arena** to create/select a session, add the promoted version,
   then start it as a separate action. No single “winner” is selected.
6. Open **Alpaca Paper Trading** to verify the simulated account and inspect or
   deliberately submit paper orders. Confirmations do not make an order real;
   they prevent accidental simulated writes.

The dashboard never calculates authoritative metrics and never calls Alpaca
directly. Experiment detail provides explicit configuration, Run, and Copy curl
controls for every validation stage and the deterministic gate. Successful
execution means evidence was recorded; only a gate result means policy
eligibility.

The states are deliberately distinct: historical candidate → Paper eligible →
Paper approved → Paper active → Paper stopped/revoked. Paper remains simulated
and cannot become Live money in this product.
## Understanding how your strategy actually traded

From a completed experiment, choose **View backtest chart**. Candles show each
period's open, high, low, and close. MA50 and MA200 are rolling average closes
using the StrategyVersion parameters; the browser does not calculate them.

A signal is known at a bar's close and can execute no earlier than the next
bar's open. Signal and BUY/SELL fill timestamps are therefore shown separately.
Selecting a fill or trade shows its price, quantity, IDs, realized P&L, and
return. The LONG/FLAT track shows invested and cash periods. The equity chart
compares the strategy with Buy & Hold under the same capital and costs.

Dataset panels distinguish requested range from actual returned coverage and
show structural diagnostics and observed bars/year. No complete exchange
coverage is claimed because an authoritative exchange calendar is not present.
Visual inspection does not replace OOS, walk-forward, sensitivity, stress,
Monte Carlo, adversarial, or validation-gate evidence.
