# ADR-001: Repository architecture

- Status: Accepted
- Date: 2026-08-14

## Context

Quant Lab requires separation between deterministic quantitative domain logic,
infrastructure, user-facing applications, and AI agents.

## Decision

Use the repository structure established by QL-001:

- Domain logic belongs under `quant/`.
- AI functionality belongs under `agents/`.
- Application entry points belong under `apps/`.
- Infrastructure belongs under `infra/`.
- Experiment artifacts belong under `experiments/`.

## Architectural rule

Dependencies should generally point inward toward deterministic domain logic.
Domain code must not depend directly on infrastructure frameworks or vendor SDKs.

## Consequences

This architecture introduces slightly more structure initially, but makes future
market-data, broker, database, and AI integrations replaceable.
