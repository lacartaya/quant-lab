# ADR-003: PostgreSQL persistence

- Status: Accepted
- Date: 2026-08-15

## Context

Quant Lab must preserve research history, failures, validation results, and
lineage across executions. The domain model must remain independent from
infrastructure.

## Decision

Use PostgreSQL with synchronous SQLAlchemy 2.x and Alembic. Explicit repository
ports separate application/domain-facing operations from SQLAlchemy adapters,
and ORM models remain distinct from domain entities. Relational foreign keys
preserve lineage, while PostgreSQL JSONB stores strategy parameters and run or
validation configuration.

Strategy versions, dataset snapshots, experiment runs, validation runs, and
promotion decisions expose append-only repository operations. Hypotheses alone
support saving state changes because their lifecycle is expected to evolve.

`MetricSet` is stored as nullable columns on `validation_runs`, with an explicit
presence flag so `None` remains distinguishable from an empty metric set. It has
no separate identity or lifecycle, so a separate table would add indirection
without preserving additional domain meaning.

## Why PostgreSQL

PostgreSQL is the initial operational database defined by the engineering
baseline and supports relational integrity, UUIDs, JSONB, reliable transactions,
and future experiment querying.

## Consequences

Persistence requires explicit mapping code between domain and ORM models, but
database concerns do not leak into the quantitative domain. Alembic migrations
are the schema authority. Integration tests require PostgreSQL, while domain and
application unit tests remain database-independent.
