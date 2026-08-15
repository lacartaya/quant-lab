# ADR-015: Deterministic validation gates

- Status: Accepted
- Date: 2026-08-15

## Context

Validation produces multidimensional evidence, but progression through the
strategy lifecycle requires explicit and auditable eligibility requirements.
Adversarial findings describe suspicious evidence; they do not define policy.

## Decision

Introduce immutable, versioned `ValidationGatePolicy` objects evaluated by
`validation-gate-v1`. The first policy identity is `HISTORICAL_TO_PAPER`; callers
must provide its version, required validation types, adversarial-report
requirement, ordered typed rules, and every threshold. The repository defines no
production thresholds.

Evidence selection is explicit: the evaluation request supplies one immutable
`ValidationType → ValidationRun ID` mapping. The engine never selects the latest
record. This mapping and each source fingerprint are stored with the result, so
new validations cannot change a historical decision.

Rules implement one of three explicit forms:

- required evidence availability;
- typed minimum/maximum thresholds over persisted metrics and aggregates;
- adversarial finding-count or forbidden-code requirements.

Metric rules with absent inputs produce a structured FAIL with
`REQUIRED_EVIDENCE_MISSING`; evaluation continues through every rule. Negative
drawdown maximums use `actual >= threshold`, so -20% passes a -25% limit and -30%
fails. Empirical Monte Carlo evidence retains its bootstrap meaning.

Gate results are stored in a dedicated append-only `gate_evaluations` table.
Each record contains the ExperimentRun and StrategyVersion, complete canonical
policy, source IDs/fingerprints, ordered rule results, decision, evaluator
version, timestamp, and SHA-256 fingerprint. Re-evaluation creates another row;
it never updates an earlier result.

Reproduction reloads the exact strategy/run, checksum-verifies the immutable
dataset, loads only the stored validation IDs, verifies their fingerprints,
reconstructs the persisted policy, reruns all rules, and compares material
results and the fingerprint. `evaluated_at` is retained for audit but excluded
from the material hash.

No strategy, hypothesis, experiment status, champion, broker, allocation, or
paper-trading state is changed by evaluation.

## Aggregation

The initial gate is strict conjunction:

```text
all required and configured rules PASS → PASS
otherwise                          → FAIL
```

There is no weighted score, compensation between rules, or early exit.

## Policy vs evidence

Validation and adversarial analysis produce evidence. Gate policies decide
whether one exact evidence snapshot satisfies one exact advancement policy.
Policy PASS means eligibility only; it is not a profitability, safety, or
deployment claim.

## Consequences

Advancement eligibility becomes reproducible, explainable, and auditable. Policy
changes require a new version and evaluation. LLMs cannot modify or override the
outcome. Paper Arena execution and lifecycle transitions remain future work.
