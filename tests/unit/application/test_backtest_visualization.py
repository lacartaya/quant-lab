from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
from uuid import UUID

import pytest

from quant.analytics import (
    AnalyticsConfiguration,
    analyze_backtest,
    buy_and_hold_benchmark,
)
from quant.application import BacktestVisualizationService, dataset_quality
from quant.application.experiments.evidence import build_evidence, evidence_fingerprint
from quant.application.experiments.registry import serialize_execution_configuration
from quant.backtest import (
    BacktestConfiguration,
    BacktestEngine,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import (
    AdjustmentPolicy,
    DatasetSnapshot,
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
    HistoricalDataset,
    MarketBar,
    StrategyVersion,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.strategies import MovingAverageParameters, MovingAverageTrendStrategy

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _fixture() -> tuple[BacktestVisualizationService, UUID, HistoricalDataset]:
    bars = tuple(
        MarketBar(
            NOW + timedelta(days=index),
            Decimal(str(close)),
            Decimal(str(close + 1)),
            Decimal(str(close - 1)),
            Decimal(str(close)),
            Decimal("1000"),
        )
        for index, close in enumerate((10, 9, 8, 10, 12, 13, 8, 7))
    )
    dataset = HistoricalDataset.from_bars(
        market="US_EQUITIES",
        instrument="SPY",
        timeframe="1Day",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=bars,
    )
    snapshot = DatasetSnapshot(
        UUID(int=1),
        "fixture",
        "US_EQUITIES",
        "SPY",
        "1Day",
        NOW - timedelta(days=1),
        NOW + timedelta(days=9),
        "ohlcv-v1",
        "sha256:test",
        "test.parquet",
        AdjustmentPolicy.RAW,
        NOW,
    )
    version = StrategyVersion(
        UUID(int=2),
        UUID(int=3),
        "v1",
        "abc",
        "moving_average_trend",
        {"short_window": 2, "long_window": 3},
        NOW,
    )
    experiment = Experiment(
        UUID(int=4),
        UUID(int=5),
        version.id,
        snapshot.id,
        ExperimentStatus.COMPLETED,
        NOW,
    )
    configuration = BacktestConfiguration(
        Decimal("10000"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
    )
    analytics = AnalyticsConfiguration(252, Decimal("0"))
    result = BacktestEngine().run(
        dataset,
        MovingAverageTrendStrategy(MovingAverageParameters(2, 3)),
        configuration,
    )
    benchmark = buy_and_hold_benchmark(dataset, configuration, analytics)
    execution = serialize_execution_configuration(configuration, analytics)
    evidence = build_evidence(
        strategy_version=version,
        dataset_snapshot=snapshot,
        execution_configuration=execution,
        backtest_result=result,
        strategy_metrics=analyze_backtest(result, analytics),
        benchmark=benchmark,
    )
    fingerprint = evidence_fingerprint(evidence)
    run = ExperimentRun(
        UUID(int=6),
        experiment.id,
        "abc",
        "backtest-engine-v1",
        "zero-fee-v1",
        "zero-slippage-v1",
        {"execution": execution, "evidence": evidence, "fingerprint": fingerprint},
        NOW,
        NOW + timedelta(minutes=1),
        ExperimentRunStatus.COMPLETED,
    )
    validation = ValidationRun(
        UUID(int=7),
        run.id,
        ValidationType.BACKTEST,
        ValidationStatus.PASSED,
        analyze_backtest(result, analytics),
        {"fingerprint": fingerprint},
        NOW,
        NOW,
    )
    experiments, strategies, datasets = Mock(), Mock(), Mock()
    experiments.get_run.return_value = run
    experiments.get.return_value = experiment
    experiments.list_validations.return_value = (validation,)
    strategies.get_version.return_value = version
    datasets.get.return_value = snapshot
    return (
        BacktestVisualizationService(
            experiments, strategies, datasets, lambda _: dataset
        ),
        run.id,
        dataset,
    )


def test_visualization_maps_exact_lineage_and_persisted_evidence() -> None:
    service, run_id, dataset = _fixture()
    value = service.build(run_id)
    bars = value["bars"]
    indicators = value["indicators"]
    fills = value["fills"]
    trades = value["trades"]
    assert isinstance(bars, tuple)
    assert isinstance(indicators, list)
    assert isinstance(fills, list)
    assert isinstance(trades, list)
    assert value["dataset_snapshot_id"] == UUID(int=1)
    assert value["strategy_version_id"] == UUID(int=2)
    assert [bar.timestamp for bar in bars] == [
        bar.timestamp for bar in dataset.bars
    ]
    assert indicators[0]["short"] == Decimal("8.5")
    assert value["indicator_labels"] == {"short": "MA2", "long": "MA3"}
    assert value["equity"]
    assert value["benchmark_equity"]
    assert all(
        fill["signal_timestamp"]
        < datetime.fromisoformat(str(fill["timestamp"]).replace("Z", "+00:00"))
        for fill in fills
    )
    assert all(
        trade["entry_order_id"] and trade["exit_order_id"] for trade in trades
    )


def test_visualization_range_is_bounded() -> None:
    service, run_id, _ = _fixture()
    with pytest.raises(ValueError, match="maximum is 3"):
        service.build(run_id, maximum_bars=3)
    value = service.build(run_id, start_at=NOW + timedelta(days=5), maximum_bars=3)
    assert value["returned_bar_count"] == 3


def test_dataset_quality_detects_duplicates_and_ordering() -> None:
    _, _, dataset = _fixture()
    bars = (dataset.bars[1], dataset.bars[0], dataset.bars[0])
    quality = dataset_quality(UUID(int=1), bars)
    assert quality.duplicate_timestamps == 1
    assert quality.non_monotonic_timestamps == 2
    assert quality.has_structural_errors
    assert not quality.exchange_calendar_verified
    assert not quality.ordering_valid
    assert quality.ohlcv_integrity_valid
    assert quality.ordering_failure_examples


def test_visualization_quality_includes_computed_boolean_statuses() -> None:
    service, run_id, _ = _fixture()
    quality = service.build(run_id)["quality"]
    assert isinstance(quality, dict)
    assert quality["ordering_valid"] is True
    assert quality["ohlcv_integrity_valid"] is True
    assert quality["has_structural_errors"] is False
