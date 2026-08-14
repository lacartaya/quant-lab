# ADR-002: Domain model

- Status: Accepted
- Date: 2026-08-15

## Context

Quant Lab requires reproducible research where every result can be traced to a
hypothesis, strategy version, dataset snapshot, experiment, and validation result.

## Decision

Introduce an infrastructure-independent domain model for hypotheses, strategies,
strategy versions, dataset snapshots, experiments, experiment runs, deterministic
metric outputs, validation runs, and promotion decisions. The model uses standard
library dataclasses, enums, UUIDs, and timezone-aware UTC timestamps.

## Key relationships

```text
Hypothesis
    │
    ↓
Experiment
    │
    ├────────→ StrategyVersion
    │
    └────────→ DatasetSnapshot
    │
    ↓
ExperimentRun
    │
    ↓
ValidationRun
    │
    ↓
MetricSet

Experiment
    │
    ↓
PromotionDecision
```

## Consequences

This establishes lineage before persistence or execution logic is introduced.
Infrastructure can later persist these objects without changing the core domain
language. Frozen historical records and immutable configuration views protect
reproducibility, while calculations and lifecycle orchestration remain outside
the model.
