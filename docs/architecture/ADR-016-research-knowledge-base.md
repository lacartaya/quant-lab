# ADR-016: Research knowledge base

- Status: Accepted
- Date: 2026-08-15

## Context

Quantitative research loses value when failed hypotheses and their tested
conditions are forgotten. Repeating materially equivalent work also wastes time
and increases multiple-testing risk.

## Decision

Use the existing relational research model as the first knowledge base.
`Hypothesis.status` remains lifecycle truth. Append-only `KnowledgeRecord`
entries preserve a contextual research signature, tested period, rejection
reason, typed reconsideration conditions, derivation lineage, and references to
experiments, runs, validations, adversarial reports, and gate evaluations.
Source quantitative evidence is referenced and never copied or recalculated.

Prior-art detection is deterministic. Exact normalized signatures are
duplicates. Same-family and same-domain records remain visible as structured
prior art. Numeric parameters are near-equivalent only under the caller's
explicit relative tolerance. Exact duplicates and near-equivalent rejected work
with unchanged reconsideration conditions are blocked; other matches return
evidence without making a research-quality decision.

Research fingerprints use canonical sorted JSON over normalized structured
fields. Material prior-art results also fingerprint the candidate,
configuration, ordered matches, reasons, and dispositions. Search ordering is
`created_at`, then record ID.

## Important principle

Knowledge is contextual. Rejection applies to its market, instrument, timeframe,
period, parameters, costs, execution model, and evidence—not universally to a
strategy family.

## Consequences

Positive and negative evidence remains searchable after restart. Reconsidered
work becomes a new hypothesis linked through `derived_from_hypothesis_id`; the
original rejection is not overwritten. Semantic similarity, embeddings, vector
databases, external literature, and AI-generated hypotheses are deferred.
