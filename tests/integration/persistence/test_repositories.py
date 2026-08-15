from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from infra.persistence.repositories import (
    SQLAlchemyDatasetRepository,
    SQLAlchemyExperimentRepository,
    SQLAlchemyHypothesisRepository,
    SQLAlchemyStrategyRepository,
)
from quant.application import RegisterExperiment
from quant.domain import (
    AdjustmentPolicy,
    DatasetSnapshot,
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
    Hypothesis,
    HypothesisStatus,
    MetricSet,
    PromotionDecision,
    PromotionDecisionType,
    Strategy,
    StrategyVersion,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.ports import ExperimentRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 15, 10, tzinfo=UTC)


def make_hypothesis() -> Hypothesis:
    return Hypothesis(
        id=uuid4(),
        title="Testable persistence hypothesis",
        description="One hypothesis",
        rationale="A rationale",
        strategy_family="trend",
        market="European equities",
        timeframe="daily",
        expected_benefit="Defined benefit",
        expected_tradeoff="Defined tradeoff",
        success_criteria="Defined success",
        rejection_criteria="Defined rejection",
        status=HypothesisStatus.REJECTED,
        reconsideration_conditions="Reconsider with a longer sample",
        created_at=NOW,
    )


def test_hypothesis_round_trip_and_lifecycle(postgres_session: Session) -> None:
    repository = SQLAlchemyHypothesisRepository(postgres_session)
    original = make_hypothesis()
    repository.add(original)

    loaded = repository.get(original.id)
    assert loaded == original
    assert loaded is not None
    assert loaded.created_at.tzinfo is not None
    assert repository.list_by_status(HypothesisStatus.REJECTED) == [original]

    updated = Hypothesis(
        id=original.id,
        title=original.title,
        description=original.description,
        rationale=original.rationale,
        strategy_family=original.strategy_family,
        market=original.market,
        timeframe=original.timeframe,
        expected_benefit=original.expected_benefit,
        expected_tradeoff=original.expected_tradeoff,
        success_criteria=original.success_criteria,
        rejection_criteria=original.rejection_criteria,
        status=HypothesisStatus.RETIRED,
        reconsideration_conditions=original.reconsideration_conditions,
        created_at=original.created_at,
    )
    repository.save(updated)
    assert repository.get(original.id) == updated


def test_complete_research_lineage_round_trip(postgres_session: Session) -> None:
    hypotheses = SQLAlchemyHypothesisRepository(postgres_session)
    strategies = SQLAlchemyStrategyRepository(postgres_session)
    datasets = SQLAlchemyDatasetRepository(postgres_session)
    experiments: ExperimentRepository = SQLAlchemyExperimentRepository(
        postgres_session
    )

    hypothesis = make_hypothesis()
    hypotheses.add(hypothesis)

    strategy = Strategy(uuid4(), "Trend", "Logical strategy", "trend", NOW)
    version = StrategyVersion(
        uuid4(),
        strategy.id,
        "v1",
        "abc123",
        "moving_average_trend",
        {"window": 20},
        NOW,
    )
    strategies.add(strategy)
    strategies.add_version(version)
    assert strategies.get(strategy.id) == strategy
    assert strategies.get_version(version.id) == version
    assert strategies.list_versions(strategy.id) == [version]

    snapshot = DatasetSnapshot(
        uuid4(),
        "example-provider",
        "European equities",
        "ABC",
        "daily",
        NOW - timedelta(days=30),
        NOW,
        "2026-08",
        "sha256:dataset",
        f"{uuid4()}/bars.parquet",
        AdjustmentPolicy.RAW,
        NOW,
    )
    datasets.add(snapshot)
    assert datasets.get(snapshot.id) == snapshot

    experiment = Experiment(
        uuid4(),
        hypothesis.id,
        version.id,
        snapshot.id,
        ExperimentStatus.CREATED,
        NOW,
    )
    RegisterExperiment(experiments)(experiment)
    assert experiments.get(experiment.id) == experiment

    run = ExperimentRun(
        uuid4(),
        experiment.id,
        "def456",
        "engine-v1",
        "fees-v1",
        "slippage-v1",
        {"seed": 42, "nested": {"enabled": True}},
        NOW,
        NOW + timedelta(minutes=5),
        ExperimentRunStatus.COMPLETED,
    )
    experiments.add_run(run)
    assert experiments.get_run(run.id) == run
    assert experiments.list_runs(experiment.id) == [run]

    metrics = MetricSet(
        total_return=0.12,
        cagr=0.08,
        max_drawdown=-0.05,
        volatility=0.15,
        sharpe=1.2,
        sortino=1.4,
        calmar=1.6,
        profit_factor=1.3,
        win_rate=0.55,
        expectancy=0.002,
        trade_count=84,
    )
    validation = ValidationRun(
        uuid4(),
        run.id,
        ValidationType.OUT_OF_SAMPLE,
        ValidationStatus.PASSED,
        metrics,
        {"fold": 1},
        NOW + timedelta(minutes=6),
        NOW + timedelta(minutes=7),
    )
    experiments.add_validation(validation)
    assert experiments.get_validation(validation.id) == validation
    assert experiments.list_validations(run.id) == [validation]

    decision = PromotionDecision(
        uuid4(),
        experiment.id,
        PromotionDecisionType.CONTINUE_TESTING,
        "More independent evidence is required.",
        NOW + timedelta(minutes=8),
    )
    experiments.add_promotion_decision(decision)
    assert experiments.list_promotion_decisions(experiment.id) == [decision]
