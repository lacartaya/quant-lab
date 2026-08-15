# ADR-017: Minimal API and operator dashboard

- Status: Accepted
- Date: 2026-08-15

## Context

Quant Lab's deterministic research capabilities need an operational interface
that does not require direct database access or Python interaction.

## Decision

Use FastAPI as a thin HTTP adapter over `OperatorQueries` and existing application
services. Explicit Pydantic schemas isolate HTTP representation from domain and
SQLAlchemy models. The versioned `/api/v1` surface exposes experiments, lineage,
runs, stored validation evidence, adversarial reports, gate evaluations,
hypotheses, research memory, and deterministic prior-art evaluation.

List selection, evidence aggregation, and resource resolution remain application
responsibilities. Routers parse inputs, invoke services, and map results. They do
not calculate metrics, run validations, mutate evidence, or issue direct SQL.
Dataset storage locations are not exposed; immutable identity, checksum, source,
period, and adjustment policy remain visible.

The operator dashboard is static HTML, CSS, and small browser JavaScript served
by the same FastAPI process. It consumes the API and only formats authoritative
numeric values for display. It contains no financial formulas, metric editing,
gate overrides, or trading controls. Missing optional evidence renders as an
empty state.

## Security

This first interface is local/internal. The Python entry point binds to
`127.0.0.1` by default. Authentication, authorization, TLS termination, and
internet exposure are not provided. Docker explicitly binds the application
inside its container and publishes only the configured API port. Credentials and
internal snapshot paths are never returned by API schemas.

## Consequences

Research becomes observable through HTTP, OpenAPI, and an operator-focused view
without introducing a second quantitative implementation. A single process is
enough for the MVP; a frontend framework, chart libraries, authentication, and
separate dashboard deployment remain unnecessary until operational needs grow.
