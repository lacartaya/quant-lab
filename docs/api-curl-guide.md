# Quant Lab curl guide

This guide covers every public operation in the current OpenAPI contract. Start
with:

```bash
export QUANT_LAB_URL=http://127.0.0.1:8000
export EXPERIMENT_ID=00000000-0000-0000-0000-000000000001
export RUN_ID=00000000-0000-0000-0000-000000000002
export VALIDATION_ID=00000000-0000-0000-0000-000000000003
export GATE_ID=00000000-0000-0000-0000-000000000004
export SNAPSHOT_ID=00000000-0000-0000-0000-000000000005
export HYPOTHESIS_ID=00000000-0000-0000-0000-000000000008
export VERSION_ID=00000000-0000-0000-0000-000000000009
export SESSION_ID=00000000-0000-0000-0000-000000000006
export PARTICIPANT_ID=00000000-0000-0000-0000-000000000007
```

Successful GET examples return JSON objects/lists with the fields named below.
Common errors are `404` unknown ID, `422` invalid parameters, `409` unsafe state
transition/confirmation/integrity conflict, and `500` unexpected internal error.
Alpaca routes additionally return `503` missing/unsafe server configuration,
`502` upstream credentials/network/server failure, `403` unavailable feed,
`429` rate limit, and `504` timeout. No request contains Alpaca credentials.

## 1. Health

**Purpose:** liveness. **GET `/health`**, no parameters.

```bash
curl "$QUANT_LAB_URL/health"
# {"status":"ok"}
```

## 2. Market Data

**Purpose:** import one Alpaca IEX US-equity daily range into an immutable
snapshot. **POST `/api/v1/market-data/import`**. Required body: provider,
instrument, market, timeframe, start/end UTC, feed, adjustment policy.

```bash
curl -X POST "$QUANT_LAB_URL/api/v1/market-data/import" \
  -H 'Content-Type: application/json' \
  --data '{"provider":"ALPACA","instrument":"SPY","market":"US_EQUITIES","timeframe":"1Day","start":"2016-01-01T00:00:00Z","end":"2026-08-01T00:00:00Z","feed":"iex","adjustment_policy":"raw"}'
# {"id":"...","provider":"ALPACA","feed":"iex","bar_count":...,"checksum":"sha256:...","storage_location":".../bars.parquet",...}
```

Errors include empty results (`404` upstream mapping), unsupported feed/timeframe
(`422`), authorization/feed denial, rate limiting, timeout, and storage failure.

## 3. Dataset Snapshots

**List** — GET, optional `limit` 1..100 and `offset`:

```bash
curl "$QUANT_LAB_URL/api/v1/datasets?limit=50&offset=0"
# {"items":[{"id":"...","provider":"ALPACA","checksum":"..."}],"page":{...}}
```

**Detail** — GET, required path `snapshot_id`:

```bash
curl "$QUANT_LAB_URL/api/v1/datasets/$SNAPSHOT_ID"
# {"id":"...","instrument":"SPY","requested_start_at":"...","storage_location":"..."}
```

## 4. Hypotheses

**List** — GET; optional `status`, `strategy_family`, `market`, `instrument`,
`timeframe`, `limit`, `offset`.

```bash
curl "$QUANT_LAB_URL/api/v1/hypotheses?market=US_EQUITIES&instrument=SPY"
# {"items":[{"id":"...","title":"...","status":"..."}],"page":{...}}
```

**Detail** — GET, required `hypothesis_id`:

```bash
curl "$QUANT_LAB_URL/api/v1/hypotheses/$HYPOTHESIS_ID"
# {"hypothesis":{...},"experiments":[...],"knowledge":[...],"derived_hypothesis_ids":[]}
```

**Create** — POST. The structured identity fields are used by deterministic
prior-art checking; exact duplicates and unchanged rejected prior art return 409.

```bash
curl -X POST "$QUANT_LAB_URL/api/v1/hypotheses" -H 'Content-Type: application/json' \
  --data '{"title":"SPY daily 50/200 trend","description":"Evaluate a 50/200 moving-average trend rule on SPY daily bars.","rationale":"Persistent trends may survive realistic execution costs.","strategy_family":"moving_average_trend","market":"US_EQUITIES","instrument":"SPY","timeframe":"1Day","parameters":{"short_window":50,"long_window":200},"expected_benefit":"Transparent trend participation","expected_tradeoff":"Whipsaw and delayed entries","success_criteria":"Reproducible validation evidence","rejection_criteria":"Insufficient robust evidence","numeric_parameter_relative_tolerance":0.02}'
# {"id":"...","status":"active_research",...}
```

## 5. Prior Art

**Purpose:** deterministic evaluation only; creates nothing. POST with all
structured identity fields and explicit tolerance:

```bash
curl -X POST "$QUANT_LAB_URL/api/v1/knowledge/prior-art-check" \
  -H 'Content-Type: application/json' \
  --data '{"strategy_family":"moving_average_trend","market":"US_EQUITIES","instrument":"SPY","timeframe":"1D","parameters":{"short_window":50,"long_window":200},"numeric_parameter_relative_tolerance":0.05}'
# {"candidate_fingerprint":"...","duplicate_detected":false,"exact_matches":[],"similar_matches":[],...}
```

## 6. Strategies / StrategyVersions

**Detail** — GET, required `version_id`:

```bash
curl "$QUANT_LAB_URL/api/v1/strategy-versions/$VERSION_ID"
# {"id":"...","algorithm_key":"moving_average_trend","parameters":{...},...}
```

**Create StrategyVersion** — POST. `algorithm_key` is resolved only through the
server-side executable registry; unknown algorithms or invalid windows return 422.

```bash
curl -X POST "$QUANT_LAB_URL/api/v1/strategy-versions" -H 'Content-Type: application/json' \
  --data '{"name":"SPY MA Trend","description":"Moving-average trend strategy","strategy_family":"moving_average_trend","version":"v1","git_commit":"operator-created","algorithm_key":"moving_average_trend","parameters":{"short_window":50,"long_window":200}}'
# {"strategy_id":"...","strategy_version_id":"...","algorithm_key":"moving_average_trend",...}
```

## 7. Experiments

**List** — GET; optional `status`, `strategy_version_id`, `hypothesis_id`,
`limit`, `offset`:

```bash
curl "$QUANT_LAB_URL/api/v1/experiments?limit=50"
# {"items":[{"experiment_id":"...","validation_coverage":[...],"latest_gate_decision":"..."}],"page":{...}}
```

**Detail** — GET, required `experiment_id`:

```bash
curl "$QUANT_LAB_URL/api/v1/experiments/$EXPERIMENT_ID"
# {"experiment":{...},"hypothesis":{...},"strategy_version":{...},"dataset_snapshot":{...},"runs":[...]}
```

**Create** — POST; every referenced ID must already exist:

```bash
curl -X POST "$QUANT_LAB_URL/api/v1/experiments" -H 'Content-Type: application/json' \
  --data "{\"hypothesis_id\":\"$HYPOTHESIS_ID\",\"strategy_version_id\":\"$VERSION_ID\",\"dataset_snapshot_id\":\"$SNAPSHOT_ID\"}"
# {"experiment_id":"...","status":"created",...}
```

**Run** — POST. Execution assumptions are explicit and persisted; this invokes
the existing deterministic `RunExperiment` service and creates BACKTEST evidence.

```bash
curl -X POST "$QUANT_LAB_URL/api/v1/experiments/$EXPERIMENT_ID/runs" \
  -H 'Content-Type: application/json' \
  --data '{"initial_cash":"10000","position_fraction":"1","fee":{"model":"percentage","rate":"0.001"},"slippage":{"model":"basis_points","basis_points":"10"},"periods_per_year":252,"annual_risk_free_rate":"0"}'
# {"experiment_run_id":"...","status":"completed","result_fingerprint":"...","validation_ids":["..."]}
```

The public workflow continues through explicit, reproducibility-safe validation
POSTs. No endpoint supplies hidden research defaults or interprets successful
execution as policy approval.

## 8. Experiment Runs

**Detail** — GET, required `run_id`:

```bash
curl "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID"
# {"id":"...","engine_version":"...","configuration":{...},"result_fingerprint":"..."}
```

## 9–14. Backtest / Metrics, OOS, Walk-Forward, Parameter Sensitivity, Stress, Monte Carlo

Execute each stage with explicit configuration:

```bash
curl -X POST "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/validations/out-of-sample" -H 'Content-Type: application/json' --data '{"training_start":"2020-07-24T00:00:00Z","training_end":"2023-12-31T23:59:59Z","test_start":"2024-01-01T00:00:00Z","test_end":"2026-08-26T23:59:59Z"}'
curl -X POST "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/validations/walk-forward" -H 'Content-Type: application/json' --data '{"mode":"expanding","training_window":504,"test_window":126,"step":126}'
curl -X POST "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/validations/parameter-sensitivity" -H 'Content-Type: application/json' --data '{"parameters":{"short_window":[40,50,60],"long_window":[180,200,220]},"maximum_combinations":9}'
curl -X POST "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/validations/stress" -H 'Content-Type: application/json' --data '{"scenarios":[{"id":"fees-2x","name":"Double fees","stress_type":"fee_multiplier","configuration":{"multiplier":"2"}}]}'
curl -X POST "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/validations/monte-carlo" -H 'Content-Type: application/json' --data '{"simulation_count":1000,"random_seed":20260831,"confidence_percentiles":[0.05,0.5,0.95],"sampling_method":"trade_bootstrap","drawdown_threshold":-0.25,"ruin_equity_fraction":0.5}'
```

OOS rejects touching or overlapping train/test ranges. Walk-forward rejects
overlapping test folds. Sensitivity stores every valid configured combination;
Monte Carlo retains the caller's seed.

All are distinct persisted validations. **List run validations** with optional
`validation_type` (`backtest`, `out_of_sample`, `walk_forward`,
`parameter_sensitivity`, `stress`, `monte_carlo`):

```bash
curl "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/validations"
curl "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/validations?validation_type=monte_carlo"
# [{"id":"...","validation_type":"...","metrics":{...},"evidence":{...}}]
```

**Validation detail** — GET, required `validation_id`:

```bash
curl "$QUANT_LAB_URL/api/v1/validations/$VALIDATION_ID"
# {"id":"...","validation_type":"stress","metrics":null,"evidence":{...}}
```

Undefined metrics remain JSON `null`; evidence includes type-specific benchmark,
fold, surface, scenario, or bootstrap structures. HTTP never recomputes them.

## 15. Adversarial

**List persisted reports for a run** — GET, required `run_id`:

```bash
curl "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/adversarial-report"
# [{"validation_type":"adversarial_review","evidence":{"report":{"findings":[...]}},...}]
```

## 16. Validation Gates

**List for run** — GET:

```bash
curl "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/gate-evaluations"
# [{"id":"...","policy_id":"HISTORICAL_TO_PAPER","decision":"pass","rule_results":[...]}]
```

**Gate detail** — GET, required `gate_id`:

```bash
curl "$QUANT_LAB_URL/api/v1/gate-evaluations/$GATE_ID"
# {"fingerprint":"...","decision_semantics":"Policy eligibility only; ...",...}
```

## 17. Research Memory

**Search** — GET; optional status/family/market/instrument/timeframe/limit/offset:

```bash
curl "$QUANT_LAB_URL/api/v1/knowledge?status=rejected&market=US_EQUITIES"
# {"items":[{"status":"rejected","rejection_reason":"...","evidence_refs":[...]}],"page":{...}}
```

**Operator summary** — GET, no parameters:

```bash
curl "$QUANT_LAB_URL/api/v1/operator-summary"
# {"active_experiments":0,"failed_gates":0,"high_findings":0,...}
```

## 18. Internal Paper Arena

All money is fake. A session uses `feed_mode` `replay` or `alpaca_iex`; execution
mode remains `internal_paper`.

```bash
# List sessions
curl "$QUANT_LAB_URL/api/v1/paper/sessions"
# Create (body fields are required)
curl -X POST "$QUANT_LAB_URL/api/v1/paper/sessions" -H 'Content-Type: application/json' \
  --data "{\"dataset_snapshot_id\":\"$SNAPSHOT_ID\",\"evaluation_start\":\"2026-08-25T00:00:00Z\",\"feed_mode\":\"replay\"}"
# Detail
curl "$QUANT_LAB_URL/api/v1/paper/sessions/$SESSION_ID"
# Add gate-eligible participant
curl -X POST "$QUANT_LAB_URL/api/v1/paper/sessions/$SESSION_ID/participants" -H 'Content-Type: application/json' --data "{\"gate_evaluation_id\":\"$GATE_ID\"}"
# Start / pause
curl -X POST "$QUANT_LAB_URL/api/v1/paper/sessions/$SESSION_ID/start"
curl -X POST "$QUANT_LAB_URL/api/v1/paper/sessions/$SESSION_ID/pause"
# Advance replay or poll IEX-forward mode
curl -X POST "$QUANT_LAB_URL/api/v1/paper/sessions/$SESSION_ID/process-next"
curl -X POST "$QUANT_LAB_URL/api/v1/paper/sessions/$SESSION_ID/poll-alpaca-iex"
```

Responses contain session identity/status or processing timestamp, participant
IDs, duplicate flag, and completion flag. Admission FAIL, wrong feed operation,
invalid lifecycle, or observation conflict returns `409`.

Participant operations:

```bash
curl "$QUANT_LAB_URL/api/v1/paper/participants/$PARTICIPANT_ID"
curl -X POST "$QUANT_LAB_URL/api/v1/paper/participants/$PARTICIPANT_ID/pause"
curl -X POST "$QUANT_LAB_URL/api/v1/paper/participants/$PARTICIPANT_ID/stop"
curl "$QUANT_LAB_URL/api/v1/paper/participants/$PARTICIPANT_ID/orders"
curl "$QUANT_LAB_URL/api/v1/paper/participants/$PARTICIPANT_ID/trades"
curl "$QUANT_LAB_URL/api/v1/paper/participants/$PARTICIPANT_ID/metrics"
```

These return participant state or immutable internal simulated artifacts. They do
not contact Alpaca Paper brokerage.

## 19. Alpaca Paper Account

```bash
curl "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/connectivity"
# {"status":"ok","broker":"alpaca","execution_environment":"paper","simulated":true,...}
curl "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/account"
# {"account_id":"...","cash":10000,"buying_power":20000,"simulated":true,...}
curl "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/fills"
# [{"activity_id":"...","order_id":"...","price":...,"simulated":true}]
```

## 20. Alpaca Paper Orders

Submit requires a stable client ID; market/day is the only supported order type.
POST writes are not blindly retried.

```bash
curl -X POST "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/orders" \
  -H 'Content-Type: application/json' \
  --data '{"symbol":"SPY","side":"buy","quantity":1,"type":"market","time_in_force":"day","client_order_id":"quant-lab-example-001"}'
# {"order_id":"...","status":"accepted","filled_quantity":0,"simulated":true,...}
curl "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/orders?status=all"
# [{"order_id":"...","status":"filled",...}]
curl "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/orders/$ORDER_ID"
# {"order_id":"...","status":"...","filled_average_price":...}
```

Errors include market closed/rejection or insufficient simulated buying power as
safe upstream messages. Always reconcile instead of assuming immediate fill.

## 21. Alpaca Paper Positions

```bash
curl "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/positions"
# [{"symbol":"SPY","quantity":1,"unrealized_pnl":...,"simulated":true}]
curl "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/positions/SPY"
# {"symbol":"SPY","average_entry_price":...,"market_value":...,"simulated":true}
curl -X DELETE "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/positions/SPY?confirm=true"
# {"order_id":"...","side":"sell","status":"...","simulated":true}
```

Omitting `confirm=true` returns `409`; an absent position returns `404`.

## 22. Alpaca live/free market-data workflow

The public forward operation is the Paper Arena poll shown in section 18. It
fetches the latest free IEX bar server-side and feeds only the named
`alpaca_iex` session. It creates Quant Lab internal simulated evidence, not an
Alpaca broker order. There is intentionally no public endpoint exposing keys or
an unrestricted vendor proxy.
## Backtest visualization and dataset quality

```bash
curl "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/backtest-visualization"
curl "$QUANT_LAB_URL/api/v1/experiment-runs/$RUN_ID/backtest-visualization?start_at=2024-01-01T00:00:00Z&end_at=2025-01-01T00:00:00Z"
curl "$QUANT_LAB_URL/api/v1/datasets/$SNAPSHOT_ID/quality"
```

Visualization is read-only and capped at 10,000 bars. Use a bounded range for
minute data. Execution and equity come from persisted evidence; supported
indicators/signals are reconstructed only server-side from immutable lineage.
