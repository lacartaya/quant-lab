from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from quant.analytics import BenchmarkResult
from quant.backtest import (
    BacktestConfiguration,
    BacktestEngine,
    BacktestResult,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import AdjustmentPolicy, HistoricalDataset, MarketBar, MetricSet
from quant.strategies import MovingAverageParameters, MovingAverageTrendStrategy
from quant.validation import (
    WalkForwardConfiguration,
    WalkForwardFold,
    WalkForwardFoldResult,
    WalkForwardMode,
    aggregate_walk_forward,
    generate_walk_forward_folds,
)


def dataset(values: tuple[str, ...], *, years: bool = False) -> HistoricalDataset:
    bars = tuple(
        MarketBar(
            timestamp=(
                datetime(2010 + index, 1, 1, tzinfo=UTC)
                if years
                else datetime(2026, 1, index + 1, tzinfo=UTC)
            ),
            open=Decimal(value),
            high=Decimal(value),
            low=Decimal(value),
            close=Decimal(value),
            volume=Decimal("1"),
        )
        for index, value in enumerate(values)
    )
    return HistoricalDataset.from_bars(
        market="test",
        instrument="ABC",
        timeframe="yearly" if years else "daily",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=bars,
    )


def test_expanding_fold_generation_golden_example() -> None:
    source = dataset(("1",) * 6, years=True)
    folds = generate_walk_forward_folds(
        source,
        WalkForwardConfiguration(WalkForwardMode.EXPANDING, 3, 1, 1),
    )

    assert [fold.id for fold in folds] == ["FOLD-001", "FOLD-002", "FOLD-003"]
    assert [
        (
            fold.training_start.year,
            fold.training_end.year,
            fold.test_start.year,
            fold.test_end.year,
        )
        for fold in folds
    ] == [
        (2010, 2012, 2013, 2013),
        (2010, 2013, 2014, 2014),
        (2010, 2014, 2015, 2015),
    ]


def test_rolling_fold_generation_golden_example() -> None:
    source = dataset(("1",) * 6, years=True)
    folds = generate_walk_forward_folds(
        source,
        WalkForwardConfiguration(WalkForwardMode.ROLLING, 3, 1, 1),
    )

    assert [
        (fold.training_start.year, fold.training_end.year, fold.test_start.year)
        for fold in folds
    ] == [
        (2010, 2012, 2013),
        (2011, 2013, 2014),
        (2012, 2014, 2015),
    ]
    assert all(
        earlier.test_end < later.test_start
        for earlier, later in zip(folds, folds[1:], strict=False)
    )


def test_configuration_is_immutable() -> None:
    configuration = WalkForwardConfiguration(WalkForwardMode.EXPANDING, 3, 1, 1)
    field_name = "training_window"
    with pytest.raises(FrozenInstanceError):
        setattr(configuration, field_name, 4)


@pytest.mark.parametrize(
    ("training", "test", "step"),
    [(0, 1, 1), (1, 0, 1), (1, 1, 0), (1, 2, 1)],
)
def test_invalid_configuration_is_rejected(
    training: int, test: int, step: int
) -> None:
    with pytest.raises(ValueError):
        WalkForwardConfiguration(WalkForwardMode.EXPANDING, training, test, step)


def test_incomplete_final_fold_is_skipped_and_zero_folds_are_rejected() -> None:
    source = dataset(("1",) * 6)
    folds = generate_walk_forward_folds(
        source,
        WalkForwardConfiguration(WalkForwardMode.EXPANDING, 3, 2, 2),
    )
    assert len(folds) == 1
    with pytest.raises(ValueError, match="zero complete folds"):
        generate_walk_forward_folds(
            source,
            WalkForwardConfiguration(WalkForwardMode.EXPANDING, 5, 2, 2),
        )


def test_warmup_context_can_queue_first_test_open_without_training_pnl() -> None:
    source = dataset(("3", "2", "5", "10", "11"))
    result = BacktestEngine().run(
        source,
        MovingAverageTrendStrategy(MovingAverageParameters(2, 3)),
        BacktestConfiguration(
            Decimal("100"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
        ),
        evaluation_start=source.bars[3].timestamp,
    )

    assert result.orders[0].timestamp == source.bars[3].timestamp
    assert result.orders[0].reference_price == Decimal("10")
    assert result.equity_curve[0].timestamp == source.bars[3].timestamp
    assert result.equity_curve[0].equity == Decimal("100")
    assert len(result.equity_curve) == 2


def test_future_changes_do_not_change_earlier_fold_execution() -> None:
    common = ("3", "2", "4", "10", "11")
    first = dataset(common + ("1", "1"))
    second = dataset(common + ("50", "60"))
    configuration = BacktestConfiguration(
        Decimal("100"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
    )
    strategy = MovingAverageTrendStrategy(MovingAverageParameters(2, 3))

    result_one = BacktestEngine().run(
        HistoricalDataset.from_bars(
            market=first.market,
            instrument=first.instrument,
            timeframe=first.timeframe,
            adjustment_policy=first.adjustment_policy,
            bars=first.bars[:5],
        ),
        strategy,
        configuration,
        evaluation_start=first.bars[3].timestamp,
    )
    result_two = BacktestEngine().run(
        HistoricalDataset.from_bars(
            market=second.market,
            instrument=second.instrument,
            timeframe=second.timeframe,
            adjustment_policy=second.adjustment_policy,
            bars=second.bars[:5],
        ),
        strategy,
        configuration,
        evaluation_start=second.bars[3].timestamp,
    )
    assert result_one == result_two


def test_aggregate_metrics_golden_example() -> None:
    results = (
        fold_result(1, 0.10, 0.05, 1.0, -0.10, 2),
        fold_result(2, -0.05, -0.02, None, -0.20, 1),
        fold_result(3, 0.20, 0.25, 2.0, -0.05, 3),
    )
    aggregate = aggregate_walk_forward(results)

    assert aggregate.fold_count == 3
    assert aggregate.profitable_fold_count == 2
    assert aggregate.profitable_fold_ratio == pytest.approx(2 / 3)
    assert aggregate.mean_total_return == pytest.approx(1 / 12)
    assert aggregate.median_total_return == 0.10
    assert aggregate.benchmark_outperformance_count == 1
    assert aggregate.worst_max_drawdown == -0.20
    assert aggregate.median_trade_count == 2


def fold_result(
    index: int,
    strategy_return: float,
    benchmark_return: float,
    sharpe: float | None,
    drawdown: float,
    trade_count: int,
) -> WalkForwardFoldResult:
    config = BacktestConfiguration(
        Decimal("100"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
    )
    backtest = BacktestResult(
        configuration=config,
        initial_cash=Decimal("100"),
        final_cash=Decimal("100"),
        final_equity=Decimal("100"),
        signals=(),
        orders=(),
        fills=(),
        trades=(),
        equity_curve=(),
        open_position=None,
        skipped_signals=(),
        unexecuted_signals=(),
    )
    fold = WalkForwardFold(
        index,
        datetime(2020, 1, 1, tzinfo=UTC),
        datetime(2020, 1, 2, tzinfo=UTC),
        datetime(2020, 1, 3, tzinfo=UTC),
        datetime(2020, 1, 4, tzinfo=UTC),
        datetime(2020, 1, 1, tzinfo=UTC),
        0,
        2,
        3,
    )
    metrics = MetricSet(
        total_return=strategy_return,
        sharpe=sharpe,
        max_drawdown=drawdown,
        trade_count=trade_count,
    )
    benchmark_metrics = MetricSet(total_return=benchmark_return)
    benchmark = BenchmarkResult("BUY_AND_HOLD", backtest, benchmark_metrics)
    return WalkForwardFoldResult(
        fold,
        "strategy-v1",
        backtest,
        metrics,
        benchmark,
        strategy_return - benchmark_return,
    )
