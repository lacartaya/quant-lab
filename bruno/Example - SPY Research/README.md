# Example - SPY Research

Run the committed requests in this order:

1. `00 - Health/Health`
2. `01 - Market Data/Import SPY Daily`
3. `02 - Datasets/Get Dataset`
4. `04 - Prior Art/Check Prior Art`
5. Select existing hypothesis/version/experiment/run IDs in the environment.
6. Run folders 03, 05, 06, 07, 08, 09, and 10 in order.
7. If an existing gate is PASS, run `12 - Paper Arena`.

Hypothesis, StrategyVersion, experiment creation, and validation execution are
not public writes in this API release, so this flow does not invent them.
