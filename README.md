# Quant Lab

Quant Lab is an AI-assisted platform for quantitative research and validation.
This repository provides deterministic strategy research, validation, research
memory, a local operator interface, Alpaca Basic market data, and simulated
paper trading. It does not provide real-money/live brokerage execution.

## Prerequisites

- Python 3.12 or newer
- Docker with Docker Compose (for PostgreSQL)

## Local setup

Create and activate a virtual environment, then install the project and its
development tools:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Copy the example environment configuration when local services need it:

```bash
cp .env.example .env
```

For Alpaca, add only PAPER credentials to the explicit `ALPACA_PAPER_*`
variables. The application rejects Alpaca's live trading URL.

`DATASET_STORAGE_PATH` selects the local root for immutable Parquet snapshots and
defaults to `./data/snapshots`. PostgreSQL stores snapshot metadata; each snapshot
stores normalized UTC OHLCV bars in `<dataset-id>/bars.parquet` and records a
canonical SHA-256 content checksum.

Run the quality checks:

```bash
ruff check .
mypy .
pytest
```

Start or stop PostgreSQL:

```bash
docker compose up -d postgres
alembic upgrade head
docker compose down
```

PostgreSQL data is retained in the named Docker volume `postgres_data`.

## Operator API and dashboard

After starting PostgreSQL and applying migrations, start the local API and
dashboard:

```bash
python -m apps.api
```

- API: `http://127.0.0.1:8000/api/v1`
- OpenAPI: `http://127.0.0.1:8000/docs`
- Dashboard: `http://127.0.0.1:8000/dashboard/`

For containerized local operation:

```bash
docker compose up --build postgres api
```

The interface supports creating hypotheses, immutable StrategyVersions and
experiments, running deterministic historical backtests, inspecting lineage,
validation and benchmark evidence, adversarial findings, gate decisions,
research-memory queries, structured prior-art checks, Alpaca historical import,
internal Paper Arena operations, and explicitly simulated Alpaca Paper actions.
It cannot edit authoritative metrics, findings, or gate results and has no
live-money controls. It is intended for local/internal use; authentication and
public deployment are not included.

Documentation:

- [Documentation index](docs/index.md)
- [Functional user guide](docs/user-guide.md)
- [Alpaca Basic and Paper guide](docs/alpaca-paper-guide.md)
- [Complete curl guide](docs/api-curl-guide.md)
- [First real SPY 50/200 research run](docs/first-real-research-run.md)
- [Bruno collection](bruno/README.md)
- Interactive OpenAPI: `http://127.0.0.1:8000/docs`
- Dashboard: `http://127.0.0.1:8000/dashboard/`

Run PostgreSQL integration tests after starting the service and applying the
migration:

```bash
pytest -m integration
```

Run only the database-independent market-data tests with:

```bash
pytest tests/unit/market_data
```

The tiny CSV fixture under `tests/fixtures/market_data/` demonstrates deterministic
CSV normalization and snapshot ingestion; it is test data, not a research sample.

## Baseline strategy

Moving Average Trend Following is currently a reference implementation used to
validate the platform architecture. It consumes normalized historical datasets
and emits deterministic `LONG` or `FLAT` state signals after its warm-up period.

The default 50/200 configuration is a non-optimized demonstration. It is not
presented as a validated trading edge and makes no performance claim.

## Deterministic backtesting

The initial backtest engine simulates a single asset with LONG/FLAT state,
integer market orders, explicit fees and deterministic slippage. Signals
generated from a completed bar are executed no earlier than the next bar open,
protecting the simulation from same-bar look-ahead assumptions.

Open positions are marked to the final close rather than forcibly liquidated.
The engine produces accounting and execution records only; it does not yet
evaluate whether a strategy is good or calculate performance statistics.

## Performance analytics

Quant Lab now derives returns, drawdown, volatility, risk-adjusted ratios, and
completed-trade metrics from deterministic backtest results. Annualization and
the risk-free rate are explicit inputs. A comparable Buy & Hold benchmark enters
at the first bar open using the same sizing and execution-cost assumptions.

Metrics describe historical simulated performance. They do not constitute
strategy validation or promotion. Exact `metrics-v1` conventions are documented
in `docs/metrics.md`.

## Experiment reproducibility

The application layer can now resolve a persisted Experiment into its exact
strategy version and immutable dataset snapshot, execute the backtest and
analytics pipeline, and persist a BACKTEST validation with its material evidence.
Behavioral inputs—including strategy parameters, costs, annualization, and all
implementation versions—are stored with the ExperimentRun.

The resulting flow is `Experiment → Run → deterministic evidence → persisted
lineage → reproduce later`. Reproduction reloads the Parquet snapshot, verifies
its checksum, reconstructs exclusively from persisted lineage, and compares a
canonical SHA-256 material-result fingerprint. A result that cannot be reproduced
is not considered valid research evidence.

## Historical validation views

- **Backtest:** how the fixed strategy behaved across a historical sample.
- **Out of sample:** how it behaved in one chronologically held-out future period.
- **Walk-forward:** how the same fixed StrategyVersion repeatedly behaved across
  multiple non-overlapping future periods.

Walk-forward validation supports expanding and rolling bar-count windows. Each
fold has independent starting capital, may use earlier bars only as signal
warm-up context, and measures strategy and Buy & Hold performance only inside its
test window. Resolved boundaries and material evidence are persisted and
fingerprinted for reproduction. These historical simulations do not prove a
durable trading edge.

## Parameter sensitivity

Parameter sensitivity asks whether a fixed strategy remains reasonably stable
when explicitly configured nearby parameters change. Quant Lab evaluates the
finite surface with identical data, execution costs, and analytics assumptions,
records every valid combination, and reports dispersion and baseline-neighbor
evidence. A narrow isolated historical optimum is more suspicious than a broad,
stable region, but the analysis makes no automatic quality decision.

Sensitivity candidates do not modify or create StrategyVersions, and the system
does not select or adopt the historically best combination. The currently
supported `FULL_HISTORY_RESEARCH` scope is explicitly research-contaminated for
future OOS interpretation.

## Stress testing

Parameter sensitivity asks what happens when strategy parameters change. Stress
testing asks what happens when execution conditions and assumptions become worse.
Quant Lab supports explicit fee and slippage multipliers, adverse fills, fixed
additional execution delay, and controlled transient parameter perturbations.

Every scenario is deterministic, retains the original dataset and baseline
lineage, and is persisted independently. Survival under stress is evidence of
historical robustness—not proof of future profitability—and stress validation
does not automatically promote or reject a strategy.

## Monte Carlo / bootstrap robustness

Stress testing asks what happens under explicitly worse assumptions. Monte Carlo
bootstrap asks what range of outcomes appears when the strategy's observed
completed-trade returns occur in different sampled sequences.

Quant Lab resamples the persisted empirical trade-return sequence with replacement
using an explicit seed, compounds each simulated path, and reports distributions
of final equity, return, drawdown, and losing streaks. Results are persisted as
independent validation evidence and can be reproduced after restart. They are
conditional empirical bootstrap results—not future-price predictions or
guarantees about future strategy performance.

## Adversarial validation

Adversarial validation does not ask, “How good does the strategy look?” It asks,
“What evidence suggests the result may be fragile or misleading?”

The deterministic analyzer consolidates already-persisted backtest, OOS,
walk-forward, parameter-sensitivity, stress, Monte Carlo, trade, and benchmark
evidence. It reports structured, source-linked findings and explicit coverage
gaps without rerunning experiments. Configured heuristics prioritize evidence;
they are not promotion decisions, PASS/FAIL gates, scores, or AI-generated advice.

## Validation gate

Validation evidence describes strategy behavior. The deterministic validation
gate decides whether one explicit evidence snapshot satisfies one specific,
versioned advancement policy. Every requirement and threshold is auditable, all
rules execute, and evaluations remain immutable when policies or evidence change.

A PASS means policy eligibility. It is not proof of future profitability or
safety, does not allocate capital, and does not start paper or live trading.

## Research memory

Quant Lab records successful and failed hypotheses together with their evidence
and tested domain. Before new research is registered, deterministic structured
prior-art checks can identify exact duplicates and materially similar work.

`REJECTED` does not mean universally invalid. It applies to the recorded market,
instrument, timeframe, period, parameters, costs, and validation evidence.

## Operator research workflow

The dashboard, REST API, curl guide, and Bruno collection support the complete
DatasetSnapshot → Hypothesis → StrategyVersion → Experiment → deterministic
BACKTEST run without direct Python or PostgreSQL access. Start with the
[SPY 50/200 walkthrough](docs/first-real-research-run.md). Later validation
execution remains explicit rather than relying on hidden operator defaults.

## Paper Arena

Historical validation uses stored historical data. Paper Arena consumes
forward-only observations and simulates orders, fills, and independent portfolios
with fake capital. Admission requires an immutable passing
`HISTORICAL_TO_PAPER` gate evaluation; passing historical validation never
authorizes real-money execution.

After starting the API, open `http://127.0.0.1:8000/dashboard/`. The versioned
`/api/v1/paper` endpoints create a replay session, admit a gate-eligible
participant, start or pause a session, and safely advance one replay bar with
`POST /api/v1/paper/sessions/{session_id}/process-next`. The dashboard displays
paper sessions, maturity, and side-by-side evidence without declaring a winner.

## Alpaca Basic data and Paper brokerage

Quant Lab can import single-symbol daily US-equity/ETF bars from Alpaca's IEX
feed into the same immutable Parquet DatasetSnapshot workflow used by CSV data.
It can also inspect and deliberately operate an Alpaca PAPER account through
PAPER-named API and dashboard controls. Alpaca-forward Paper Arena sessions use
IEX observations with Quant Lab's internal fake fills; they do not route strategy
orders to Alpaca automatically.

Alpaca Basic IEX coverage is not the consolidated US SIP feed, and Alpaca paper
fills remain simulations. No configuration switch, endpoint, adapter, or UI
control can send a real-money Alpaca order.

All tests, including fast domain tests, can be run with `pytest`. If PostgreSQL
is unavailable, integration tests are skipped while unit tests still run.
