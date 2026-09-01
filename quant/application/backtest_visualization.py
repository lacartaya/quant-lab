from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from quant.application.experiments.registry import build_strategy
from quant.domain import (
    ExperimentRunStatus,
    HistoricalDataset,
    MarketBar,
    ValidationStatus,
    ValidationType,
)
from quant.ports import DatasetRepository, ExperimentRepository, StrategyRepository

MAX_VISUALIZATION_BARS = 10_000


class BacktestVisualizationUnavailable(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class DatasetQuality:
    snapshot_id: UUID
    actual_start_at: datetime
    actual_end_at: datetime
    total_bars: int
    duplicate_timestamps: int
    non_monotonic_timestamps: int
    ohlc_validity_failures: int
    missing_ohlcv_values: int
    ordering_failure_examples: tuple[Mapping[str, object], ...]
    ohlcv_failure_examples: tuple[Mapping[str, object], ...]
    bars_by_calendar_year: Mapping[int, int]
    exchange_calendar_verified: bool = False

    @property
    def ordering_valid(self) -> bool:
        return self.duplicate_timestamps == 0 and self.non_monotonic_timestamps == 0

    @property
    def ohlcv_integrity_valid(self) -> bool:
        return self.ohlc_validity_failures == 0 and self.missing_ohlcv_values == 0

    @property
    def has_structural_errors(self) -> bool:
        return not self.ordering_valid or not self.ohlcv_integrity_valid

    def as_evidence(self) -> dict[str, object]:
        """Return the complete API shape, including computed status fields."""
        return {
            "snapshot_id": self.snapshot_id,
            "actual_start_at": self.actual_start_at,
            "actual_end_at": self.actual_end_at,
            "total_bars": self.total_bars,
            "duplicate_timestamps": self.duplicate_timestamps,
            "non_monotonic_timestamps": self.non_monotonic_timestamps,
            "ordering_valid": self.ordering_valid,
            "ordering_failure_examples": list(self.ordering_failure_examples),
            "ohlc_validity_failures": self.ohlc_validity_failures,
            "missing_ohlcv_values": self.missing_ohlcv_values,
            "ohlcv_integrity_valid": self.ohlcv_integrity_valid,
            "ohlcv_failure_examples": list(self.ohlcv_failure_examples),
            "bars_by_calendar_year": dict(self.bars_by_calendar_year),
            "exchange_calendar_verified": self.exchange_calendar_verified,
            "completeness_note": (
                "Observed bars only; completeness has not been verified against "
                "an authoritative exchange calendar."
            ),
            "has_structural_errors": self.has_structural_errors,
        }


def dataset_quality(snapshot_id: UUID, bars: Sequence[MarketBar]) -> DatasetQuality:
    if not bars:
        raise ValueError("dataset quality requires at least one bar")
    timestamps = [bar.timestamp for bar in bars]
    duplicate_count = len(timestamps) - len(set(timestamps))
    ordering_failures = [
        {"index": index, "previous": previous, "current": current}
        for index, (previous, current) in enumerate(
            zip(timestamps, timestamps[1:], strict=False), start=1
        )
        if current <= previous
    ]
    invalid_bars = [
        {
            "index": index,
            "timestamp": bar.timestamp,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for index, bar in enumerate(bars)
        if bar.high < max(bar.open, bar.low, bar.close)
        or bar.low > min(bar.open, bar.high, bar.close)
        or bar.volume < 0
    ]
    years = Counter(timestamp.year for timestamp in timestamps)
    return DatasetQuality(
        snapshot_id=snapshot_id,
        actual_start_at=min(timestamps),
        actual_end_at=max(timestamps),
        total_bars=len(bars),
        duplicate_timestamps=duplicate_count,
        non_monotonic_timestamps=len(ordering_failures),
        ohlc_validity_failures=len(invalid_bars),
        missing_ohlcv_values=0,
        ordering_failure_examples=tuple(ordering_failures[:5]),
        ohlcv_failure_examples=tuple(invalid_bars[:5]),
        bars_by_calendar_year=dict(sorted(years.items())),
    )


@dataclass(frozen=True, slots=True)
class BacktestVisualizationService:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]

    def build(
        self,
        run_id: UUID,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        maximum_bars: int = MAX_VISUALIZATION_BARS,
    ) -> dict[str, object]:
        run = self.experiments.get_run(run_id)
        if run is None:
            raise BacktestVisualizationUnavailable(f"experiment run {run_id} not found")
        if run.status is not ExperimentRunStatus.COMPLETED:
            raise BacktestVisualizationUnavailable("experiment run is not completed")
        experiment = self.experiments.get(run.experiment_id)
        if experiment is None:
            raise BacktestVisualizationUnavailable("experiment lineage is missing")
        version = self.strategies.get_version(experiment.strategy_version_id)
        snapshot = self.datasets.get(experiment.dataset_snapshot_id)
        if version is None or snapshot is None:
            raise BacktestVisualizationUnavailable("experiment lineage is missing")
        validation = next(
            (
                item
                for item in self.experiments.list_validations(run_id)
                if item.validation_type is ValidationType.BACKTEST
                and item.status is ValidationStatus.PASSED
            ),
            None,
        )
        evidence = run.configuration.get("evidence")
        if validation is None or not isinstance(evidence, Mapping):
            raise BacktestVisualizationUnavailable(
                "completed BACKTEST evidence is unavailable"
            )
        lineage = self._mapping(evidence, "lineage")
        if lineage.get("strategy_version_id") != str(version.id) or lineage.get(
            "dataset_snapshot_id"
        ) != str(snapshot.id):
            raise ValueError("backtest evidence does not match requested run lineage")
        dataset = self.dataset_loader(snapshot.id)
        selected = tuple(
            bar
            for bar in dataset.bars
            if (start_at is None or bar.timestamp >= start_at)
            and (end_at is None or bar.timestamp <= end_at)
        )
        if not selected:
            raise ValueError("requested visualization range contains no bars")
        if len(selected) > maximum_bars:
            raise ValueError(
                f"visualization range contains {len(selected)} bars; "
                f"maximum is {maximum_bars}"
            )
        strategy = build_strategy(version)
        indicators = strategy.indicator_series(dataset)
        signals = strategy.generate_signals(dataset)
        backtest = self._mapping(evidence, "backtest")
        benchmark = self._mapping(evidence, "benchmark_backtest")
        start = selected[0].timestamp
        end = selected[-1].timestamp

        def in_range(value: Mapping[str, object]) -> bool:
            return start <= self._timestamp(value) <= end

        fills = [dict(item) for item in self._list(backtest, "fills") if in_range(item)]
        for fill in fills:
            fill_timestamp = self._timestamp(fill)
            expected_action = "long" if fill.get("side") == "buy" else "flat"
            source = next(
                (
                    signal
                    for signal in reversed(signals)
                    if signal.timestamp < fill_timestamp
                    and signal.action.value == expected_action
                ),
                None,
            )
            fill["signal_timestamp"] = source.timestamp if source else None
            fill["order_eligible_timestamp"] = fill.get("timestamp")
        trades = self._trades(self._list(backtest, "trades"), fills)
        execution = self._mapping(lineage, "execution_configuration")
        quality = dataset_quality(snapshot.id, dataset.bars)
        return {
            "run_id": run.id,
            "experiment_id": experiment.id,
            "strategy_version_id": version.id,
            "dataset_snapshot_id": snapshot.id,
            "result_fingerprint": run.configuration.get("fingerprint"),
            "instrument": snapshot.instrument,
            "timeframe": snapshot.timeframe,
            "strategy": version.algorithm_key,
            "parameters": dict(version.parameters),
            "requested_start_at": snapshot.start_at,
            "requested_end_at": snapshot.end_at,
            "actual_start_at": quality.actual_start_at,
            "actual_end_at": quality.actual_end_at,
            "bar_count": quality.total_bars,
            "returned_bar_count": len(selected),
            "maximum_bar_count": maximum_bars,
            "execution": dict(execution),
            "bars": selected,
            "indicators": [
                {
                    "timestamp": point.timestamp,
                    "short": point.short_average,
                    "long": point.long_average,
                }
                for point in indicators
                if start <= point.timestamp <= end
            ],
            "indicator_labels": {
                "short": f"MA{version.parameters['short_window']}",
                "long": f"MA{version.parameters['long_window']}",
            },
            "signals": [
                signal for signal in signals if start <= signal.timestamp <= end
            ],
            "orders": [
                item for item in self._list(backtest, "orders") if in_range(item)
            ],
            "fills": fills,
            "trades": trades,
            "positions": self._position_periods(fills, end),
            "equity": [
                item for item in self._list(backtest, "equity_curve") if in_range(item)
            ],
            "benchmark_equity": [
                item for item in self._list(benchmark, "equity_curve") if in_range(item)
            ],
            "quality": quality.as_evidence(),
        }

    @staticmethod
    def _mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
        found = value.get(key)
        if not isinstance(found, Mapping):
            raise ValueError(f"persisted {key} evidence is missing")
        return found

    @staticmethod
    def _list(value: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
        found = value.get(key)
        if not isinstance(found, list) or not all(
            isinstance(item, Mapping) for item in found
        ):
            raise ValueError(f"persisted {key} evidence is missing")
        return [item for item in found if isinstance(item, Mapping)]

    @staticmethod
    def _timestamp(value: Mapping[str, object]) -> datetime:
        timestamp = value.get("timestamp")
        if not isinstance(timestamp, str):
            timestamp = value.get("entry_timestamp")
        if not isinstance(timestamp, str):
            raise ValueError("persisted evidence timestamp is missing")
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    @classmethod
    def _trades(
        cls, values: list[Mapping[str, object]], fills: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        fill_by_key = {
            (item.get("timestamp"), item.get("side")): item for item in fills
        }
        result = []
        for index, item in enumerate(values, 1):
            trade = dict(item)
            entry_capital = Decimal(str(item["entry_price"])) * Decimal(
                str(item["quantity"])
            ) + Decimal(str(item["entry_fees"]))
            entry_fill = fill_by_key.get((item.get("entry_timestamp"), "buy"), {})
            exit_fill = fill_by_key.get((item.get("exit_timestamp"), "sell"), {})
            entry_timestamp = cls._timestamp({"timestamp": item["entry_timestamp"]})
            exit_timestamp = cls._timestamp({"timestamp": item["exit_timestamp"]})
            realized_pnl = Decimal(str(item["realized_pnl"]))
            trade.update(
                {
                    "id": f"TRADE-{index:06d}",
                    "entry_order_id": entry_fill.get("order_id"),
                    "exit_order_id": exit_fill.get("order_id"),
                    "entry_signal_timestamp": entry_fill.get("signal_timestamp"),
                    "exit_signal_timestamp": exit_fill.get("signal_timestamp"),
                    "return": str(realized_pnl / entry_capital),
                    "duration_seconds": int(
                        (exit_timestamp - entry_timestamp).total_seconds()
                    ),
                    "outcome": "winning" if realized_pnl >= 0 else "losing",
                }
            )
            result.append(trade)
        return result

    @staticmethod
    def _position_periods(
        fills: list[dict[str, object]], final_timestamp: datetime
    ) -> list[dict[str, object]]:
        periods: list[dict[str, object]] = []
        entry: str | None = None
        for fill in fills:
            if fill.get("side") == "buy":
                entry = str(fill["timestamp"])
            elif fill.get("side") == "sell" and entry is not None:
                periods.append(
                    {"state": "long", "start_at": entry, "end_at": fill["timestamp"]}
                )
                entry = None
        if entry is not None:
            periods.append(
                {"state": "long", "start_at": entry, "end_at": final_timestamp}
            )
        return periods
