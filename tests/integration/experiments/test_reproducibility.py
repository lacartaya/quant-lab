from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from infra.market_data import LocalParquetDatasetStorage
from infra.persistence.repositories import (
    SQLAlchemyDatasetRepository,
    SQLAlchemyExperimentRepository,
    SQLAlchemyHypothesisRepository,
    SQLAlchemyStrategyRepository,
)
from quant.analytics import AnalyticsConfiguration
from quant.application import DatasetIntegrityError, LoadDatasetSnapshot
from quant.application.experiments import (
    ReproduceExperiment,
    ReproduceParameterSensitivityValidation,
    ReproduceStressValidation,
    ReproduceWalkForwardValidation,
    RunExperiment,
    RunParameterSensitivityValidation,
    RunStressValidation,
    RunWalkForwardValidation,
)
from quant.application.experiments.evidence import canonical_value
from quant.backtest import (
    BacktestConfiguration,
    BasisPointsSlippageModel,
    PercentageFeeModel,
)
from quant.domain import (
    AdjustmentPolicy,
    DatasetSnapshot,
    Experiment,
    ExperimentRunStatus,
    ExperimentStatus,
    Hypothesis,
    HypothesisStatus,
    MarketBar,
    Strategy,
    StrategyVersion,
    ValidationStatus,
    ValidationType,
)
from quant.validation import (
    ParameterSensitivityConfiguration,
    ParameterSpaceTooLarge,
    StressScenario,
    StressTestingConfiguration,
    StressType,
    WalkForwardConfiguration,
    WalkForwardMode,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 15, 10, tzinfo=UTC)


def _bars() -> tuple[MarketBar, ...]:
    closes = ("3", "2", "1", "4", "5", "1", "1", "1")
    return tuple(
        MarketBar(
            timestamp=NOW + timedelta(days=index),
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=Decimal("100"),
        )
        for index, close in enumerate(closes)
    )


def _persist_lineage(session: Session, root: Path) -> Experiment:
    hypotheses = SQLAlchemyHypothesisRepository(session)
    strategies = SQLAlchemyStrategyRepository(session)
    datasets = SQLAlchemyDatasetRepository(session)
    experiments = SQLAlchemyExperimentRepository(session)
    hypothesis = Hypothesis(
        uuid4(),
        "A reproducible trend hypothesis",
        "Test a small deterministic example.",
        "Establish lineage.",
        "trend",
        "US equities",
        "daily",
        "Transparent evidence",
        "False signals",
        "Reproducible output",
        "Non-reproducible output",
        HypothesisStatus.ACTIVE_RESEARCH,
        None,
        NOW,
    )
    strategy = Strategy(uuid4(), "Moving average trend", "Baseline", "trend", NOW)
    version = StrategyVersion(
        uuid4(),
        strategy.id,
        "v1",
        "abc123",
        "moving_average_trend",
        {"short_window": 2, "long_window": 3},
        NOW,
    )
    bars = _bars()
    snapshot_id = uuid4()
    storage = LocalParquetDatasetStorage(root)
    location = storage.write(snapshot_id, bars)
    from quant.application import canonical_bars_checksum

    snapshot = DatasetSnapshot(
        snapshot_id,
        "test-fixture",
        "US equities",
        "ABC",
        "daily",
        bars[0].timestamp,
        bars[-1].timestamp + timedelta(microseconds=1),
        "ohlcv-v1",
        canonical_bars_checksum(bars),
        location,
        AdjustmentPolicy.RAW,
        NOW,
    )
    experiment = Experiment(
        uuid4(),
        hypothesis.id,
        version.id,
        snapshot.id,
        ExperimentStatus.CREATED,
        NOW,
    )
    hypotheses.add(hypothesis)
    strategies.add(strategy)
    strategies.add_version(version)
    datasets.add(snapshot)
    experiments.add(experiment)
    return experiment


def _services(
    session: Session, root: Path
) -> tuple[RunExperiment, ReproduceExperiment]:
    experiments = SQLAlchemyExperimentRepository(session)
    strategies = SQLAlchemyStrategyRepository(session)
    datasets = SQLAlchemyDatasetRepository(session)
    loader = LoadDatasetSnapshot(LocalParquetDatasetStorage(root), datasets)
    return (
        RunExperiment(
            experiments,
            SQLAlchemyHypothesisRepository(session),
            strategies,
            datasets,
            loader,
        ),
        ReproduceExperiment(experiments, strategies, datasets, loader),
    )


def test_golden_experiment_persists_and_reproduces_from_a_fresh_session(
    postgres_session: Session, tmp_path: Path
) -> None:
    experiment = _persist_lineage(postgres_session, tmp_path)
    runner, _ = _services(postgres_session, tmp_path)
    execution = runner.execute(
        experiment.id,
        BacktestConfiguration(
            Decimal("100"),
            Decimal("1"),
            PercentageFeeModel(Decimal("0.001")),
            BasisPointsSlippageModel(Decimal("10")),
        ),
        AnalyticsConfiguration(365, Decimal("0.025")),
    )
    fresh_session = Session(bind=postgres_session.connection(), expire_on_commit=False)
    try:
        _, reproducer = _services(fresh_session, tmp_path)
        reproduced = reproducer.execute(execution.experiment_run_id)
        repository = SQLAlchemyExperimentRepository(fresh_session)
        stored_run = repository.get_run(execution.experiment_run_id)
        validations = repository.list_validations(execution.experiment_run_id)
    finally:
        fresh_session.close()

    assert reproduced.matches
    assert reproduced.mismatches == ()
    assert reproduced.original_fingerprint == reproduced.reproduced_fingerprint
    assert reproduced.backtest_result.orders == execution.backtest_result.orders
    assert reproduced.backtest_result.fills == execution.backtest_result.fills
    assert reproduced.backtest_result.trades == execution.backtest_result.trades
    assert (
        reproduced.backtest_result.equity_curve
        == execution.backtest_result.equity_curve
    )
    assert reproduced.strategy_metrics == execution.strategy_metrics
    assert reproduced.benchmark == execution.benchmark
    assert stored_run is not None
    assert stored_run.status is ExperimentRunStatus.COMPLETED
    assert len(validations) == 1
    assert validations[0].validation_type is ValidationType.BACKTEST
    assert validations[0].status is ValidationStatus.PASSED
    assert canonical_value(validations[0].metric_set) == canonical_value(
        execution.strategy_metrics
    )


def test_reproduction_refuses_a_mutated_dataset(
    postgres_session: Session, tmp_path: Path
) -> None:
    experiment = _persist_lineage(postgres_session, tmp_path)
    runner, reproducer = _services(postgres_session, tmp_path)
    execution = runner.execute(
        experiment.id,
        BacktestConfiguration(
            Decimal("100"),
            Decimal("1"),
            PercentageFeeModel(Decimal("0")),
            BasisPointsSlippageModel(Decimal("0")),
        ),
        AnalyticsConfiguration(252),
    )
    snapshot = SQLAlchemyDatasetRepository(postgres_session).get(
        execution.dataset_snapshot_id
    )
    assert snapshot is not None
    (tmp_path / snapshot.storage_location).write_bytes(b"mutated evidence")

    with pytest.raises(DatasetIntegrityError):
        reproducer.execute(execution.experiment_run_id)


def test_failed_execution_is_persisted_as_failed(
    postgres_session: Session, tmp_path: Path
) -> None:
    experiment = _persist_lineage(postgres_session, tmp_path)
    runner, _ = _services(postgres_session, tmp_path)
    snapshot = SQLAlchemyDatasetRepository(postgres_session).get(
        experiment.dataset_snapshot_id
    )
    assert snapshot is not None
    (tmp_path / snapshot.storage_location).write_bytes(b"broken")

    with pytest.raises(DatasetIntegrityError):
        runner.execute(
            experiment.id,
            BacktestConfiguration(
                Decimal("100"),
                Decimal("1"),
                PercentageFeeModel(Decimal("0")),
                BasisPointsSlippageModel(Decimal("0")),
            ),
            AnalyticsConfiguration(252),
        )

    runs = SQLAlchemyExperimentRepository(postgres_session).list_runs(experiment.id)
    assert len(runs) == 1
    assert runs[0].status is ExperimentRunStatus.FAILED
    assert runs[0].configuration["failure_reason"]


def test_walk_forward_persists_and_reproduces_from_a_fresh_session(
    postgres_session: Session, tmp_path: Path
) -> None:
    experiment = _persist_lineage(postgres_session, tmp_path)
    runner, _ = _services(postgres_session, tmp_path)
    execution = runner.execute(
        experiment.id,
        BacktestConfiguration(
            Decimal("100"),
            Decimal("1"),
            PercentageFeeModel(Decimal("0.001")),
            BasisPointsSlippageModel(Decimal("10")),
        ),
        AnalyticsConfiguration(252, Decimal("0.01")),
    )
    experiments = SQLAlchemyExperimentRepository(postgres_session)
    strategies = SQLAlchemyStrategyRepository(postgres_session)
    datasets = SQLAlchemyDatasetRepository(postgres_session)
    loader = LoadDatasetSnapshot(LocalParquetDatasetStorage(tmp_path), datasets)
    validation = RunWalkForwardValidation(
        experiments, strategies, datasets, loader
    ).execute(
        execution.experiment_run_id,
        WalkForwardConfiguration(WalkForwardMode.EXPANDING, 3, 2, 2),
    )

    fresh_session = Session(bind=postgres_session.connection(), expire_on_commit=False)
    try:
        fresh_experiments = SQLAlchemyExperimentRepository(fresh_session)
        fresh_strategies = SQLAlchemyStrategyRepository(fresh_session)
        fresh_datasets = SQLAlchemyDatasetRepository(fresh_session)
        fresh_loader = LoadDatasetSnapshot(
            LocalParquetDatasetStorage(tmp_path), fresh_datasets
        )
        reproduced = ReproduceWalkForwardValidation(
            fresh_experiments,
            fresh_strategies,
            fresh_datasets,
            fresh_loader,
        ).execute(validation.validation_run_id)
        persisted = fresh_experiments.list_validations(
            execution.experiment_run_id
        )
    finally:
        fresh_session.close()

    assert reproduced.matches
    assert reproduced.mismatches == ()
    assert reproduced.reproduced_fingerprint == validation.fingerprint
    assert reproduced.result.fold_results == validation.fold_results
    assert reproduced.result.aggregate == validation.aggregate
    assert len(validation.fold_results) == 2
    assert all(
        fold.strategy_version_id == str(execution.strategy_version_id)
        for fold in validation.fold_results
    )
    assert all(
        fold.backtest_result.initial_cash == Decimal("100")
        for fold in validation.fold_results
    )
    assert [item.validation_type for item in persisted] == [
        ValidationType.BACKTEST,
        ValidationType.WALK_FORWARD,
    ]


def test_parameter_sensitivity_preserves_strategy_and_reproduces_after_restart(
    postgres_session: Session, tmp_path: Path
) -> None:
    experiment = _persist_lineage(postgres_session, tmp_path)
    runner, _ = _services(postgres_session, tmp_path)
    execution = runner.execute(
        experiment.id,
        BacktestConfiguration(
            Decimal("100"),
            Decimal("1"),
            PercentageFeeModel(Decimal("0.001")),
            BasisPointsSlippageModel(Decimal("10")),
        ),
        AnalyticsConfiguration(252, Decimal("0.01")),
    )
    experiments = SQLAlchemyExperimentRepository(postgres_session)
    strategies = SQLAlchemyStrategyRepository(postgres_session)
    datasets = SQLAlchemyDatasetRepository(postgres_session)
    loader = LoadDatasetSnapshot(LocalParquetDatasetStorage(tmp_path), datasets)
    before_versions = strategies.list_versions(execution.strategy_version.strategy_id)
    sensitivity_runner = RunParameterSensitivityValidation(
        experiments, strategies, datasets, loader
    )
    with pytest.raises(ParameterSpaceTooLarge):
        sensitivity_runner.execute(
            execution.experiment_run_id,
            ParameterSensitivityConfiguration(
                {"short_window": (1, 2), "long_window": (3, 4)},
                maximum_combinations=3,
            ),
        )
    assert [
        item.validation_type
        for item in experiments.list_validations(execution.experiment_run_id)
    ] == [ValidationType.BACKTEST]
    sensitivity = sensitivity_runner.execute(
        execution.experiment_run_id,
        ParameterSensitivityConfiguration(
            {"short_window": (1, 2), "long_window": (3, 4)},
            maximum_combinations=4,
        ),
    )
    after_versions = strategies.list_versions(execution.strategy_version.strategy_id)

    fresh_session = Session(bind=postgres_session.connection(), expire_on_commit=False)
    try:
        fresh_experiments = SQLAlchemyExperimentRepository(fresh_session)
        fresh_strategies = SQLAlchemyStrategyRepository(fresh_session)
        fresh_datasets = SQLAlchemyDatasetRepository(fresh_session)
        fresh_loader = LoadDatasetSnapshot(
            LocalParquetDatasetStorage(tmp_path), fresh_datasets
        )
        reproduced = ReproduceParameterSensitivityValidation(
            fresh_experiments,
            fresh_strategies,
            fresh_datasets,
            fresh_loader,
        ).execute(sensitivity.validation_run_id)
        persisted = fresh_experiments.list_validations(
            execution.experiment_run_id
        )
    finally:
        fresh_session.close()

    assert before_versions == after_versions
    assert reproduced.matches
    assert reproduced.mismatches == ()
    assert reproduced.reproduced_fingerprint == sensitivity.fingerprint
    assert reproduced.result.analysis == sensitivity.analysis
    assert len(sensitivity.analysis.candidates) == 4
    assert sum(
        item.combination.is_baseline for item in sensitivity.analysis.candidates
    ) == 1
    assert all(
        item.backtest_result.configuration
        == execution.backtest_result.configuration
        for item in sensitivity.analysis.candidates
    )
    assert [item.validation_type for item in persisted] == [
        ValidationType.BACKTEST,
        ValidationType.PARAMETER_SENSITIVITY,
    ]
    evaluation = persisted[1].configuration["evaluation"]
    assert isinstance(evaluation, dict)
    assert evaluation["scope"] == "full_history_research"
    assert evaluation["contaminates_future_oos_interpretation"] is True


def test_stress_suite_is_cost_monotonic_and_reproduces_after_restart(
    postgres_session: Session, tmp_path: Path
) -> None:
    experiment = _persist_lineage(postgres_session, tmp_path)
    runner, _ = _services(postgres_session, tmp_path)
    execution = runner.execute(
        experiment.id,
        BacktestConfiguration(
            Decimal("100"),
            Decimal("1"),
            PercentageFeeModel(Decimal("0.001")),
            BasisPointsSlippageModel(Decimal("10")),
        ),
        AnalyticsConfiguration(252, Decimal("0.01")),
    )
    experiments = SQLAlchemyExperimentRepository(postgres_session)
    strategies = SQLAlchemyStrategyRepository(postgres_session)
    datasets = SQLAlchemyDatasetRepository(postgres_session)
    loader = LoadDatasetSnapshot(LocalParquetDatasetStorage(tmp_path), datasets)
    before_versions = strategies.list_versions(execution.strategy_version.strategy_id)
    stress = RunStressValidation(experiments, strategies, datasets, loader).execute(
        execution.experiment_run_id,
        StressTestingConfiguration(
            (
                StressScenario(
                    "STRESS-FEES-2X",
                    "Fees doubled",
                    StressType.FEE_MULTIPLIER,
                    {"multiplier": Decimal("2")},
                ),
                StressScenario(
                    "STRESS-FEES-3X",
                    "Fees tripled",
                    StressType.FEE_MULTIPLIER,
                    {"multiplier": Decimal("3")},
                ),
                StressScenario(
                    "STRESS-SLIPPAGE-2X",
                    "Slippage doubled",
                    StressType.SLIPPAGE_MULTIPLIER,
                    {"multiplier": Decimal("2")},
                ),
                StressScenario(
                    "STRESS-DELAY-1",
                    "One additional bar delay",
                    StressType.EXECUTION_DELAY,
                    {"additional_delay_bars": 1},
                ),
                StressScenario(
                    "STRESS-ADVERSE-10BPS",
                    "Additional adverse execution",
                    StressType.ADVERSE_PRICE,
                    {"additional_basis_points": Decimal("10")},
                ),
                StressScenario(
                    "STRESS-PARAMETERS-A",
                    "Explicit parameter perturbation",
                    StressType.PARAMETER_PERTURBATION,
                    {"parameters": {"short_window": 1, "long_window": 3}},
                ),
            )
        ),
    )
    after_versions = strategies.list_versions(execution.strategy_version.strategy_id)
    by_id = {
        result.scenario.id: result for result in stress.analysis.scenario_results
    }
    assert (
        stress.analysis.baseline_backtest.final_equity
        >= by_id["STRESS-FEES-2X"].backtest_result.final_equity
        >= by_id["STRESS-FEES-3X"].backtest_result.final_equity
    )
    assert (
        stress.analysis.baseline_backtest.final_equity
        >= by_id["STRESS-SLIPPAGE-2X"].backtest_result.final_equity
    )
    assert before_versions == after_versions

    fresh_session = Session(bind=postgres_session.connection(), expire_on_commit=False)
    try:
        fresh_experiments = SQLAlchemyExperimentRepository(fresh_session)
        fresh_strategies = SQLAlchemyStrategyRepository(fresh_session)
        fresh_datasets = SQLAlchemyDatasetRepository(fresh_session)
        fresh_loader = LoadDatasetSnapshot(
            LocalParquetDatasetStorage(tmp_path), fresh_datasets
        )
        reproduced = ReproduceStressValidation(
            fresh_experiments,
            fresh_strategies,
            fresh_datasets,
            fresh_loader,
        ).execute(stress.validation_run_id)
        persisted = fresh_experiments.list_validations(
            execution.experiment_run_id
        )
    finally:
        fresh_session.close()

    assert reproduced.matches
    assert reproduced.mismatches == ()
    assert reproduced.reproduced_fingerprint == stress.fingerprint
    assert reproduced.result.analysis == stress.analysis
    assert [item.validation_type for item in persisted] == [
        ValidationType.BACKTEST,
        ValidationType.STRESS,
    ]
