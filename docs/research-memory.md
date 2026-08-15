# Research memory

Quant Lab uses the relational hypothesis and evidence lineage as its first
knowledge base. `HypothesisStatus` remains authoritative: `KNOWN_REPLICATED`,
`ACTIVE_RESEARCH`, `VALIDATED_INTERNAL`, `REJECTED`, and `RETIRED` retain their
existing meanings. None implies production approval.

## Rejection and reconsideration

A rejection is an explicit workflow, not an automatic consequence of a failed
gate. Its append-only record includes the tested domain and period, strategy
parameters, reason, evidence references, and optional typed conditions:

- `NEW_MARKET`
- `NEW_TIMEFRAME`
- `NEW_EXECUTION_MODEL`
- `MATERIALLY_NEW_EVIDENCE`
- `MATERIALLY_NEW_STRATEGY_LOGIC`
- `DIFFERENT_COST_MODEL`
- `DIFFERENT_REGIME_SCOPE`

The checker can establish structured field changes. New evidence and new
strategy logic require an explicit external assertion in a future workflow;
free text is not interpreted semantically. Meeting a condition permits
reconsideration but does not validate the new idea.

Reconsidered work is a new hypothesis with `derived_from_hypothesis_id`. The old
rejection remains unchanged.

## Prior-art matching

Research signatures contain strategy family, market, instrument, timeframe,
parameters, and optional execution, cost, and regime identifiers. Text fields
are case-folded and whitespace-normalized. Parameter keys are sorted.

- `EXACT`: every normalized structured field is identical; registration blocks.
- `SIMILAR_PARAMETERS`: same family/domain and numeric differences are inside the
  explicit relative tolerance.
- `SAME_DOMAIN`: family and domain match, but parameters materially differ.
- `SAME_STRATEGY_FAMILY`: related work in another domain.

Near-equivalent rejected work blocks only while no declared reconsideration
condition has changed. Other matches provide explainable evidence, not automatic
rejection. No global family blacklist exists.

## Evidence and auditability

Evidence references identify experiments, runs, validations, adversarial
reports, and gate evaluations. Rejection validates each reference before
persistence. Prior-art results preserve the tolerance, ordered matches, match
reasons, dispositions, and a canonical SHA-256 fingerprint. Structured search
supports family, market, instrument, timeframe, status, and combinations with
stable ordering.
