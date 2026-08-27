# Example - SPY Research

Run the committed requests in this order:

1. `00 - Health/Health`
2. `01 - Market Data/Import SPY Daily`
3. `02 - Datasets/Get Dataset`
4. `04 - Prior Art/Check Prior Art`
5. `03 - Hypotheses/Create Hypothesis` (captures `hypothesisId`).
6. `05 - Strategies/Create StrategyVersion` (captures `versionId`).
7. `06 - Experiments/Create Experiment` (captures `experimentId`).
8. `06 - Experiments/Run Experiment` (captures `runId` and BACKTEST `validationId`).
9. `07 - Experiment Runs/Get Run` and `08 - Validations/List All Validations`.
10. Inspect the automatically persisted BACKTEST validation.

The HTTP API does not yet expose the OOS, walk-forward, sensitivity, stress,
Monte Carlo, adversarial-generation, or gate-evaluation application services.
Their existing evidence remains readable through folders 08–10. This sequence
does not invent hidden validation or gate configuration.
