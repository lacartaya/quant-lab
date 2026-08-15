# Validation gates

## Policy model

`ValidationGatePolicy` contains:

- immutable policy ID and positive version;
- descriptive name;
- ordered required validation types;
- an explicit adversarial-report requirement;
- ordered typed rule definitions and thresholds.

`HISTORICAL_TO_PAPER` is the initial policy identity. Changing any threshold or
requirement creates a new version; an old version remains historical truth.

Callers explicitly select each source ValidationRun ID. Multiple records of one
type are therefore never resolved through a mutable “latest” convention.

## Rule ordering and missing evidence

Results are ordered as:

1. required validations in policy order;
2. required adversarial report, if configured;
3. configured rules in policy order.

Every rule executes. Missing metric evidence returns FAIL with
`REQUIRED_EVIDENCE_MISSING`; it does not crash or stop later rules.

## Supported rule codes

| Source | Minimum rules (`actual >= threshold`) | Maximum rules |
|---|---|---|
| OOS MetricSet | `MIN_OOS_RETURN`, `MIN_OOS_SHARPE`, `MIN_OOS_TRADE_COUNT` | `MAX_OOS_DRAWDOWN` uses signed `actual >= threshold` |
| Walk-forward aggregate | `MIN_WALK_FORWARD_PROFITABLE_FOLD_RATIO`, `MIN_WALK_FORWARD_MEDIAN_SHARPE`, `MIN_WALK_FORWARD_BENCHMARK_OUTPERFORMANCE_RATIO` | `MAX_WALK_FORWARD_SHARPE_DISPERSION` uses `actual <= threshold` |
| Parameter sensitivity | `MIN_PARAMETER_PROFITABLE_RATIO` | `MAX_PARAMETER_SHARPE_DISPERSION`, `MAX_BASELINE_NEIGHBOR_SHARPE_DELTA` |
| Stress aggregate | `MIN_STRESS_PROFITABLE_RATIO`, `MIN_WORST_STRESS_RETURN` | `MAX_WORST_STRESS_DRAWDOWN` uses signed `actual >= threshold` |
| Monte Carlo distribution | `MIN_MONTE_CARLO_P05_RETURN` | `MAX_MONTE_CARLO_LOSS_FREQUENCY`, `MAX_MONTE_CARLO_LOSS_STREAK`; `MAX_MONTE_CARLO_ADVERSE_DRAWDOWN` uses signed `actual >= threshold` |
| Adversarial report | — | `MAX_HIGH_ADVERSARIAL_FINDINGS`, `MAX_WARNING_ADVERSARIAL_FINDINGS`, `FORBIDDEN_ADVERSARIAL_FINDING` |

Required evidence codes are generated stably as `REQUIRED_<VALIDATION_TYPE>`.
Monte Carlo values remain empirical bootstrap evidence, not future probabilities.

## EXAMPLE / NON-PRODUCTION policy

```text
policy_id: HISTORICAL_TO_PAPER
version: 1
required: BACKTEST, OUT_OF_SAMPLE, WALK_FORWARD,
          PARAMETER_SENSITIVITY, STRESS, MONTE_CARLO
require_adversarial_report: true

MIN_OOS_SHARPE                              >= 0.50
MAX_OOS_DRAWDOWN                            >= -0.25
MIN_WALK_FORWARD_PROFITABLE_FOLD_RATIO      >= 0.60
MIN_STRESS_PROFITABLE_RATIO                 >= 0.50
MAX_MONTE_CARLO_LOSS_FREQUENCY              <= 0.30
MAX_HIGH_ADVERSARIAL_FINDINGS               <= 0
```

These values exist only to illustrate mechanics. They are not approved financial
or production promotion thresholds.

## Decision and reproduction semantics

PASS means the challenger satisfied this exact policy version using this exact
evidence snapshot. It does not mean the strategy is safe, profitable, suitable
for capital, or deployed.

Each append-only evaluation stores its policy, source IDs/fingerprints, all rule
results, overall decision, and `validation-gate-v1` fingerprint. Reproduction
verifies source and dataset integrity and reconstructs exclusively from those
stored inputs. New evidence and current defaults cannot change the old result.

No AI override or weighted score exists.
