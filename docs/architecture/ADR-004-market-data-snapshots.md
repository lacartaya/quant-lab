# ADR-004: Market-data snapshots

- Status: Accepted
- Date: 2026-08-15

## Context

Quant Lab requires reproducible historical research and must protect against
silent dataset mutation or provider-specific coupling.

## Decision

- Historical OHLCV data enters through a `MarketDataProvider` port.
- CSV is the initial deterministic provider adapter.
- Bars use timezone-aware UTC timestamps and `Decimal` prices and volume.
- Normalized bars form an immutable, chronologically ordered dataset with unique
  timestamps.
- Historical data is stored as immutable Parquet snapshots through a small
  storage port; local filesystem storage is the initial adapter.
- PostgreSQL stores snapshot metadata and relational lineage, while Parquet stores
  the observations.
- Every snapshot records its relative storage location and an explicit `RAW` or
  `ADJUSTED` policy.
- A SHA-256 checksum is calculated from a canonical normalized representation of
  the bars, not raw Parquet bytes. This keeps identity stable across input row
  order, equivalent decimal formatting, timezone spelling, temporary paths, and
  compatible Parquet-library changes.

PyArrow is confined to the infrastructure storage adapter. The domain and
application boundaries use explicit `MarketBar` tuples and do not expose tables
or dataframes.

## Rationale

Experiments can reference exact immutable data without coupling research logic
to a particular market-data vendor or serialization library. Canonical content
hashing expresses logical dataset identity more reliably than claiming Parquet
bytes are stable across all library versions.

## Consequences

The platform manages PostgreSQL metadata and file/object storage as separate
resources. Snapshot loading verifies content before returning it, and modified or
unreadable data fails explicitly. Future providers and storage adapters can be
added without changing experiment logic.

No bars are synthesized or forward-filled, invalid OHLC data is not repaired,
and adjustment policy is never inferred.
