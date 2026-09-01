# QL-026 local runtime acceptance — 2026-08-31

Authoritative evidence is persisted in PostgreSQL and the immutable
`quant-lab_dataset_snapshots` Docker volume. This file is the operator summary.

- Old IEX snapshot: `1d8c025b-5b24-453a-833f-edc9e177e01b`
- New SIP snapshot: `47492346-df65-4919-b27d-a1d3f1f4b554`
- Experiment: `f09dd57e-a519-4363-a979-4771655af5b4`
- Final ExperimentRun: `2b23693f-3d87-4d05-b5f5-362e3fe831d2`
- Gate evaluation: `6aefc62f-0e24-4fa7-93ee-f5fb403e5223` (`pass`)

## Dataset forensics

Alpaca's read-only IEX response for the original requested range exactly matches
the old Parquet: one bar on 2018-11-01 (OHLC 271.60, volume 200), no 2019 bars,
and 2020 beginning on 2020-07-27. The file has 1,530 strictly ascending unique
timestamps and no OHLCV integrity failures. This is IEX historical coverage, not
Parquet corruption, pagination, or reordering.

The SIP-entitled response produced 2,677 bars from 2016-01-04 through 2026-08-26.
It has no duplicate/non-monotonic timestamps or OHLCV failures. Annual counts are
252, 251, 251, 252, 253, 252, 251, 250, 252, 250, and 163 for 2016–2026.

## Backtest comparison

| Metric | Old IEX | New SIP |
|---|---:|---:|
| Total return | 65.0841% | 135.8422% |
| CAGR | 8.6069% | 8.4119% |
| Max drawdown | -18.9347% | -33.7570% |
| Volatility | 12.1193% | 14.1653% |
| Sharpe | 0.7418 | 0.6414 |
| Sortino | 1.0705 | 0.8816 |
| Calmar | 0.4546 | 0.2492 |
| Completed trades | 2 | 4 |
| Buy & Hold total return | 181.9171% | 276.9425% |

## Validation evidence

- OOS `f81e2967-053b-4633-ac45-e7340911d8be`: return 61.2809%, Sharpe
  0.9988, drawdown -18.8680%, one completed trade.
- Walk-forward `a749cf13-b3ff-45d8-81c2-5e09315daa1b`: 17 folds, 70.5882%
  profitable, median return 6.2727%, median Sharpe 1.0901, Sharpe dispersion
  1.3223, benchmark outperformance 23.5294%.
- Sensitivity `c2f41b48-cb7b-44c1-998c-52bfcdb1d76f`: all 9 combinations
  profitable; median return 134.9776%, median Sharpe 0.6414, Sharpe dispersion
  0.0337, baseline-neighbor Sharpe delta 0.0262.
- Stress `b4597fae-9ebc-4043-9ca2-78140ae7ef2e`: all 4 scenarios profitable;
  worst return 124.6745%, worst drawdown -34.0784%, worst Sharpe 0.6041.
- Monte Carlo `a0d2a62a-f00e-4ce6-9961-7d183d670c68`: 1,000 paths from four
  completed-trade observations; p05 return 23.4084%, loss frequency 4.9%, severe
  drawdown frequency 2.2%, ruin frequency 0%.
- Adversarial `6b360827-80cc-41e8-9d11-1544b4ebb329`: zero high and five warning
  findings—top-three profit concentration, OOS return drop, low total/OOS trade
  counts, and high walk-forward Sharpe dispersion.

The documented example `HISTORICAL_TO_PAPER` policy passed every explicit rule.
That is acceptance under this exact policy only, not proof of a durable edge.

## Runtime defects fixed

1. Canonicalize OOS temporal-separation datetimes before evidence fingerprinting.
2. Normalize documented stress JSON decimal fields at the API boundary.
3. Make the PostgreSQL API integration assertion independent of pre-existing data.
4. Expand all Bruno request blocks to valid multiline Bru syntax.

