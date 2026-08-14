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

Run the quality checks:

```bash
ruff check .
mypy .
pytest
```

Start or stop PostgreSQL:

```bash
docker compose up -d postgres
docker compose down
```

PostgreSQL data is retained in the named Docker volume `postgres_data`.
