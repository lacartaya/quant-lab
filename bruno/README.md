# Quant Lab Bruno collection

Install [Bruno](https://www.usebruno.com/), open this `bruno/` directory as a
collection, and select the `local` environment. Start PostgreSQL and Quant Lab,
then run **00 - Health / Health**.

The collection contains one request for every current public OpenAPI operation.
It is organized in research order: market-data import, immutable datasets,
hypotheses/prior art, experiments, validation, gate, knowledge, internal Paper
Arena, and Alpaca Paper. IDs are environment variables. Import captures
`snapshotId`; research creation captures `hypothesisId`, `versionId`,
`experimentId`, `runId`, and the BACKTEST `validationId`; paper operations
capture their own returned IDs.

## Example - SPY Research

Run Health, import/list SPY Daily, check prior art, create the hypothesis, create
the immutable MA 50/200 StrategyVersion, create the experiment, and run it. Each
write captures the ID required by the next request. The run creates and captures
BACKTEST evidence. Later validation-generation services are not yet public HTTP
writes; their persisted evidence remains inspectable in folders 08–10. If an
immutable PASS gate exists, the Paper Arena workflow can admit it.

## Example - Alpaca Paper Trading

Run Connectivity, Account, Submit SPY Buy, Get Order, List Orders, List
Positions, Get SPY Position, Close SPY Position, and List Fills. These are
educational simulated-account writes and are never run by normal automated
tests. Use small quantities and inspect market status/order state.

Bruno never needs Alpaca keys. It calls Quant Lab at `baseUrl`; Quant Lab keeps
the paper keys server-side. No secret is committed in either environment.
