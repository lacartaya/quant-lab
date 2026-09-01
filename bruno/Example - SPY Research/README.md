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
10. Run the explicit POST requests in `08 - Validations` in sequence.
11. Run `09 - Adversarial/Get Report`.
12. Run `10 - Validation Gates/Run Gate` and retain PASS or FAIL honestly.
13. Inspect the visualization and Dataset Quality endpoints.

Each request captures its immutable evidence ID for the next stage. Review every
configuration before execution; example values are not approved thresholds or
optimized strategy parameters.
