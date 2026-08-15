# ADR-008: Experiment reproducibility

- Status: Accepted
- Date: 2026-08-15

## Context

Quant Lab cannot treat a backtest result as research evidence unless it can be
traced to exact code, data, parameters, execution assumptions, and calculation
versions and reproduced later. Current application defaults are not historical
lineage and must never reinterpret an earlier experiment.

## Decision

Introduce application-level `RunExperiment` and `ReproduceExperiment` services.
They coordinate repository ports, immutable dataset loading, strategy
construction, backtesting, analytics, and benchmarking; no formula or execution
logic moves into the application or persistence layers.

`StrategyVersion` records a stable `algorithm_key` in addition to its parameters,
version, and Git commit. A small explicit registry reconstructs the supported
`moving_average_trend` algorithm. Similar explicit resolution protects
`backtest-engine-v1`, fee and slippage model versions, and `metrics-v1`; an
unknown historical implementation fails rather than silently falling forward.

`ExperimentRun.configuration` stores behaviorally relevant execution lineage:
initial cash, position fraction, fee identity and parameters, slippage identity
and parameters, annualization periods, annual risk-free rate, analytics version,
and Buy & Hold benchmark identity. A completed run also stores canonical material
evidence and its SHA-256 fingerprint. Its BACKTEST `ValidationRun` stores the
strategy `MetricSet` and benchmark metrics.

Dataset loading verifies the immutable snapshot checksum and metadata range
before execution. Reproduction builds solely from stored lineage, recomputes the
strategy and benchmark, and compares orders, fills, trades, equity curve, final
equity, both metric sets, and lineage. Exact `Decimal` values use stable decimal
strings; timestamps use UTC ISO-8601; JSON keys are sorted. Database timestamps
and runtime diagnostics are excluded from the material comparison.

## Reproducibility invariant

A material experiment result resolves to:

- Hypothesis;
- StrategyVersion, algorithm key, parameters, and Git commit;
- DatasetSnapshot, immutable storage location, and checksum;
- BacktestEngine version and BacktestConfiguration;
- fee model version and configuration;
- slippage model version and configuration;
- analytics version and configuration;
- strategy metrics;
- Buy & Hold benchmark metrics and execution evidence.

## Consequences

Historical experiments remain explainable when defaults change. Completed
evidence is append-oriented, while a run has only the small RUNNING to
COMPLETED/FAILED lifecycle needed to avoid abandoned RUNNING records. Supporting
older experiments may eventually require retaining historical implementations;
QL-008 only detects unsupported versions and does not invent them.
