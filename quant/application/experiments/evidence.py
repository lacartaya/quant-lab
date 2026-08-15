import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, cast

from quant.analytics import BenchmarkResult
from quant.backtest import BacktestResult
from quant.domain import DatasetSnapshot, MetricSet, StrategyVersion


def build_evidence(
    *,
    strategy_version: StrategyVersion,
    dataset_snapshot: DatasetSnapshot,
    execution_configuration: Mapping[str, object],
    backtest_result: BacktestResult,
    strategy_metrics: MetricSet,
    benchmark: BenchmarkResult,
) -> dict[str, object]:
    return {
        "lineage": {
            "strategy_version_id": str(strategy_version.id),
            "algorithm_key": strategy_version.algorithm_key,
            "strategy_parameters": canonical_value(strategy_version.parameters),
            "git_commit": strategy_version.git_commit,
            "dataset_snapshot_id": str(dataset_snapshot.id),
            "dataset_checksum": dataset_snapshot.checksum,
            "execution_configuration": canonical_value(execution_configuration),
        },
        "backtest": backtest_material(backtest_result),
        "strategy_metrics": canonical_value(strategy_metrics),
        "benchmark_name": benchmark.name,
        "benchmark_backtest": backtest_material(benchmark.backtest_result),
        "benchmark_metrics": canonical_value(benchmark.metrics),
    }


def backtest_material(result: BacktestResult) -> dict[str, object]:
    return {
        "final_cash": canonical_value(result.final_cash),
        "final_equity": canonical_value(result.final_equity),
        "orders": canonical_value(result.orders),
        "fills": canonical_value(result.fills),
        "trades": canonical_value(result.trades),
        "equity_curve": canonical_value(result.equity_curve),
        "open_position": canonical_value(result.open_position),
    }


def evidence_fingerprint(evidence: Mapping[str, object]) -> str:
    encoded = json.dumps(
        evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def canonical_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return "0" if value == 0 else format(value.normalize(), "f")
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Enum):
        return canonical_value(value.value)
    if isinstance(value, Mapping):
        return {
            str(key): canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [canonical_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: canonical_value(getattr(value, field.name))
            for field in fields(cast(Any, value))
        }
    raise TypeError(f"cannot canonicalize {type(value).__name__}")
