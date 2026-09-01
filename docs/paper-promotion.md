# Paper promotion

Paper promotion is the explicit human boundary between completed historical
research and forward-only observation with fake capital.

```text
Historical validation → Gate PASS → Paper eligible → human approval
→ Paper approved → separate session/participant/start actions → Paper evidence
```

A Gate PASS means only that one exact evidence snapshot met one exact versioned
policy. It does not guarantee an edge and is not Paper approval. Paper approval
does not start a session. A running Paper session is still simulated and is not
Live money.

## Eligibility and approval

The application—not the browser—checks that the completed ExperimentRun exists,
the selected `HISTORICAL_TO_PAPER` gate belongs to that exact run and is PASS,
the gate StrategyVersion matches the experiment, and the immutable
DatasetSnapshot can still be checksum-verified. Missing or invalid lineage fails
closed.

Approval requires `confirm: true`, a reason, and an internal operator marker.
The resulting `PaperPromotion` captures the hypothesis, exact StrategyVersion,
experiment/run, gate and policy version, dataset, actor, reason, and timestamps.
An identical request returns the existing approved promotion. A revoked lineage
cannot be re-approved: a new gate decision is required, preserving temporal
audit history.

Revocation prevents new participants. It does not delete completed sessions,
Paper observations, or historical gate evidence. Gate or policy changes after
approval never rewrite the old decision.

## Paper operation

Participant admission requires an approved, non-revoked promotion and rejects a
different StrategyVersion or any broker target. Session feed, evaluation start,
fake initial capital, costs, and execution assumptions remain explicit evidence.
Replay and Alpaca-IEX forward observations both use Quant Lab internal simulated
fills. Direct Alpaca PAPER broker endpoints remain a separate manual facility.

There is no Paper-to-Live promotion, Live broker, Live URL, or automatic broker
order routing.

> Historical research and Paper Promotion feature freeze.

The next phase is operational learning and accumulated Paper observation—not
Live-money implementation.
