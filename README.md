# Quant Lab

Quant Lab is an AI-assisted platform for quantitative research and validation.
This repository currently provides its engineering foundation; it does not yet
contain strategies, backtesting, integrations, or live-trading functionality.

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

All tests, including fast domain tests, can be run with `pytest`. If PostgreSQL
is unavailable, integration tests are skipped while unit tests still run.
