# ADR-019: Alpaca Basic market data and paper brokerage

## Context

Quant Lab previously obtained historical OHLCV only from local CSV files and its
Paper Arena consumed only deterministic replay. Operators need real historical
US-equity data and simulated external brokerage without introducing real-money
execution.

## Decision

Add Alpaca behind existing ports and application boundaries:

- `AlpacaHistoricalMarketDataProvider` implements `MarketDataProvider`, starts
  with single-symbol daily and one-minute US-equity/ETF bars, paginates, and
  requests IEX.
- Imports pass through the existing `HistoricalDataset` validation,
  `CreateDatasetSnapshot`, checksum, local Parquet storage, and PostgreSQL
  metadata. The immutable provider identity `alpaca:iex` records feed provenance.
- `AlpacaLiveMarketDataProvider` implements the polling
  `LiveMarketDataProvider` port using latest one-minute IEX bars. Paper Arena may
  consume these bars with a compatible one-minute warm-up snapshot but continues
  to use Quant Lab's internal simulated execution.
- `AlpacaPaperBrokerAdapter` implements the paper-only broker port and maps
  account, order, fill, and position responses into explicit `AlpacaPaper*`
  DTOs. Initial orders are market/day BUY or SELL orders.
- Broker writes are never automatically retried. Caller-provided
  `client_order_id` preserves reconciliation identity. Idempotent historical GETs
  use bounded backoff for 429 and server errors.

The only permitted trading origin is exactly
`https://paper-api.alpaca.markets`. The only market-data origin is exactly
`https://data.alpaca.markets`. Configuration validation rejects the live trading
origin; paper credentials use explicit `ALPACA_PAPER_*` names. Browser and Bruno
clients call Quant Lab and never receive Alpaca credentials.

## Paper modes

- Replay Paper Arena: stored snapshot bars, Quant Lab simulated fills.
- Alpaca IEX forward Paper Arena: polled IEX bars, Quant Lab simulated fills.
- Alpaca Paper brokerage: operator-submitted orders go to Alpaca's simulated
  paper account and are queried/reconciled by external order ID.

These modes are deliberately named and displayed separately. Paper Arena does
not silently route its strategy orders to Alpaca.

## Free-plan constraints

Alpaca Basic equities real-time data is IEX rather than consolidated SIP
coverage. Availability, rate limits, market hours, and subscription permissions
remain controlled by Alpaca and errors are surfaced without secrets. The import
does not claim a universal earliest date; the requested and actual returned
ranges are both reported.

## Consequences

Strategies and backtests remain vendor-independent. Real Alpaca checks are
opt-in, normal tests use mocked HTTP, and there is still no adapter, URL,
configuration switch, API, or dashboard control capable of submitting a
real-money Alpaca order.
