# ADR-014: Adversarial validation

- Status: Accepted
- Date: 2026-08-15

## Context

Individual validation techniques may appear acceptable in isolation while their
combined evidence reveals instability, concentration, weak generalization, or
dependence on favorable assumptions.

## Decision

Introduce `adversarial-analyzer-v1`, a deterministic analyzer that consumes
persisted validation artifacts and produces immutable, machine-readable findings.
It executes no strategies, backtests, parameter searches, stress scenarios, or
bootstrap simulations.

The analyzer evaluates available evidence for:

- generalization;
- temporal stability;
- parameter robustness;
- execution robustness;
- sequence risk;
- profit concentration;
- sample size;
- benchmark context;
- validation coverage.

Every heuristic threshold is supplied through an explicit immutable
`AdversarialAnalysisConfiguration`. Thresholds prioritize suspicious evidence;
they are not promotion gates. Findings have stable codes, structured evidence,
source ValidationRun IDs, and only `INFO`, `WARNING`, or `HIGH` severity. They do
not produce PASS, FAIL, PROMOTE, REJECT, a score, or a grade.

Missing validations create coverage gaps and INFO findings, not strategy
failures. The current repository has no QL-009 OOS execution service, so OOS
checks are implemented and tested against the existing domain/persistence shape
but naturally remain absent until an OUT_OF_SAMPLE record exists.

Derived reports are appended as `ValidationType.ADVERSARIAL_REVIEW`. JSONB stores
the analyzer version, exact configuration, source validation IDs and
fingerprints, report, and canonical SHA-256 fingerprint. Reproduction loads only
those original source records, verifies their fingerprints and the immutable
DatasetSnapshot, reruns the deterministic rules, and compares material evidence.
No source validation is overwritten.

Trade concentration uses completed trades from canonical BacktestResult evidence.
Shares use net positive realized P&L divided by total positive realized P&L, not
unstable net profit after losses. Top-three concentration is evaluated only when
at least three winning trades exist. Fold-return concentration is deferred
because independently reset walk-forward capital makes continuous-P&L language
misleading.

## AI boundary

LLMs may later explain the structured report, but may not calculate authoritative
findings, alter evidence, or substitute generated interpretation for deterministic
metrics and checks.

## Consequences

Quant Lab gains a standardized falsification-oriented view before deterministic
promotion eligibility is designed. A new database check-constraint migration
allows the append-only derived validation type. Future rule changes require a new
analyzer version so old evidence is not silently reinterpreted.
