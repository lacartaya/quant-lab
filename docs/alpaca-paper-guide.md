# Alpaca Basic and Paper guide

Everything described here is simulated trading. Quant Lab has no Alpaca live
trading integration.

## 1. Create and configure the paper account

Create an Alpaca account, open its Paper Trading environment, and create paper
API credentials. Paper and live keys are different; use only the paper pair.
Copy `.env.example` to `.env` and set:

```dotenv
ALPACA_PAPER_API_KEY=your-paper-key
ALPACA_PAPER_API_SECRET=your-paper-secret
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets
ALPACA_MARKET_DATA_BASE_URL=https://data.alpaca.markets
ALPACA_MARKET_DATA_FEED=iex
```

Quant Lab rejects Alpaca's live trading URL. Keys are server-side only and are
never entered in the dashboard, curl, OpenAPI, or Bruno.

## 2. Start and verify

Start PostgreSQL, migrate, and run the API as described in the README. Open
`http://127.0.0.1:8000/dashboard/`, find **Alpaca Paper Trading**, and select
**Verify connection**. The account is prominently labeled PAPER / SIMULATED.

Equivalent command:

```bash
curl "$QUANT_LAB_URL/api/v1/brokers/alpaca/paper/connectivity"
```

Invalid credentials, subscription/feed denial, rate limiting, timeout, unknown
resources, and order rejection are returned as structured API errors without
keys or stack traces.

## 3. Import real historical SPY data

In **Market Data / Datasets**, choose SPY, Daily, start, and end. The dashboard
calls Quant Lab, not Alpaca. Quant Lab requests paginated IEX bars, validates
OHLCV, writes an immutable Parquet file, and records PostgreSQL metadata and a
SHA-256 checksum. The result shows requested and actual ranges because holidays,
market sessions, entitlements, and data availability can differ from a request.

Initial support is one US equity/ETF symbol, daily or one-minute bars, IEX, and
raw or adjusted bars. One-minute import supplies warm-up for an Alpaca-forward
Paper Arena session. Crypto, options, multi-symbol imports, and SIP are not
included.

## 4. Research with the snapshot

Use the returned DatasetSnapshot ID in the existing hypothesis, strategy,
experiment, validation, adversarial, and gate workflows. Some creation/run
workflows remain application-service operations and are not yet public write
APIs; the dashboard and API expose all persisted evidence. A gate FAIL is valid
research evidence and must not be changed to force paper eligibility.

## 5. Alpaca paper orders

The dashboard can show simulated account balances, positions, recent orders,
and fills. It can submit small market/day BUY or SELL paper orders. Every write
requires confirmation. Closing a position calls the PAPER-only endpoint with
`confirm=true`.

Orders are not assumed filled immediately. Read the returned status and refresh
the order by its Alpaca order ID. Typical states include submitted/accepted,
partially filled, filled, canceled, and rejected as returned by Alpaca.
Quant Lab does not blindly retry POST orders; the caller supplies a stable
`client_order_id` for safe reconciliation.

## 6. Paper Arena

Paper Arena remains a separate Quant Lab simulator. A session can use replay or
`alpaca_iex` forward bars. In the latter mode, Alpaca supplies observations but
Quant Lab produces internal fake fills. Paper Arena does not automatically send
strategy orders to the Alpaca paper account. The current latest-bar polling
adapter emits one-minute bars, so an `alpaca_iex` session requires a compatible
one-minute warm-up snapshot; it never relabels a minute bar as a daily bar.

## Basic/free limitations

For US equities, Alpaca Basic real-time coverage uses IEX, not the full
consolidated US SIP feed. IEX prices and volume therefore represent only that
venue and can differ from consolidated quotes. Alpaca controls current data
history, request limits, permissions, market hours, and simulated-broker
behavior. Paper fills are simulations and are not evidence that the same order
would fill in a real market.

Alpaca's current plan documentation describes Basic as free, historical equity
coverage from 2016, a 200 historical-request-per-minute allowance, and restricted
access to the most recent SIP data. Quant Lab deliberately requests `feed=iex`,
uses bounded retry on read-only 429 responses, and reports the actual returned
range instead of assuming that every symbol/feed begins on the advertised date.

## Optional acceptance checks

Normal pytest never calls Alpaca. Set `RUN_ALPACA_INTEGRATION_TESTS=true` to opt
into read-only account/data checks. Any test that submits a paper order must also
require `RUN_ALPACA_PAPER_ORDER_TESTS=true`; do not enable that flag casually.
