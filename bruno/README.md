# Quant Lab Bruno collection

Install [Bruno](https://www.usebruno.com/), open this `bruno/` directory as a
collection, and select the `local` environment. Start PostgreSQL and Quant Lab,
then run **00 - Health / Health**.

The collection contains one request for every current public OpenAPI operation.
It is organized in research order: market-data import, immutable datasets,
hypotheses/prior art, experiments, validation, gate, knowledge, internal Paper
Arena, and Alpaca Paper. IDs are environment variables. Import captures
`snapshotId`; paper-session/participant/order creates capture their returned IDs.
Set persisted research IDs manually where the current API is read-only.

## Example - SPY Research

Run Health, Import SPY Daily, Get Dataset, Check Prior Art, then select existing
hypothesis/version/experiment/run IDs and inspect all validation, adversarial,
and gate requests. The current public API does not create or execute the full
research pipeline; the collection states this gap instead of faking requests.
If an immutable PASS gate exists, create an internal Paper Arena session and add
its participant.

## Example - Alpaca Paper Trading

Run Connectivity, Account, Submit SPY Buy, Get Order, List Orders, List
Positions, Get SPY Position, Close SPY Position, and List Fills. These are
educational simulated-account writes and are never run by normal automated
tests. Use small quantities and inspect market status/order state.

Bruno never needs Alpaca keys. It calls Quant Lab at `baseUrl`; Quant Lab keeps
the paper keys server-side. No secret is committed in either environment.
