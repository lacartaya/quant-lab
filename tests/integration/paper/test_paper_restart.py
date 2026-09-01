from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from infra.persistence.repositories import (
    SQLAlchemyDatasetRepository,
    SQLAlchemyExperimentRepository,
    SQLAlchemyGateRepository,
    SQLAlchemyHypothesisRepository,
    SQLAlchemyPaperPromotionRepository,
    SQLAlchemyPaperRepository,
    SQLAlchemyStrategyRepository,
)
from quant.analytics import AnalyticsConfiguration
from quant.application import (
    AddPaperParticipant,
    PaperLifecycle,
    PaperPromotionService,
    ProcessPaperBar,
)
from quant.application.dataset_snapshots import canonical_bars_checksum
from quant.application.experiments.registry import serialize_execution_configuration
from quant.backtest import BacktestConfiguration, ZeroFeeModel, ZeroSlippageModel
from quant.domain import (
    AdjustmentPolicy,
    DatasetSnapshot,
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
    GateDecision,
    HistoricalDataset,
    Hypothesis,
    HypothesisStatus,
    MarketBar,
    PaperSession,
    PaperSessionStatus,
    Strategy,
    StrategyVersion,
    ValidationGateResult,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 19, tzinfo=UTC)


def test_paper_processing_reloads_and_continues_without_duplicate_evidence(
    postgres_session: Session,
) -> None:
    bars = tuple(
        MarketBar(
            NOW + timedelta(days=index),
            Decimal(price),
            Decimal(price),
            Decimal(price),
            Decimal(price),
            Decimal("100"),
        )
        for index, price in enumerate(("10", "11", "12", "8", "7"))
    )
    source = HistoricalDataset.from_bars(
        market="US_EQUITIES",
        instrument="SPY",
        timeframe="1D",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=bars,
    )
    hypotheses = SQLAlchemyHypothesisRepository(postgres_session)
    strategies = SQLAlchemyStrategyRepository(postgres_session)
    datasets = SQLAlchemyDatasetRepository(postgres_session)
    experiments = SQLAlchemyExperimentRepository(postgres_session)
    gates = SQLAlchemyGateRepository(postgres_session)
    papers = SQLAlchemyPaperRepository(postgres_session)
    promotions = SQLAlchemyPaperPromotionRepository(postgres_session)

    hypothesis = Hypothesis(
        uuid4(),
        "Paper restart",
        "Forward replay",
        "Rationale",
        "trend",
        "US_EQUITIES",
        "1D",
        "Evidence",
        "Risk",
        "Observe",
        "Reject",
        HypothesisStatus.VALIDATED_INTERNAL,
        None,
        NOW,
    )
    strategy = Strategy(uuid4(), "MA", "Paper fixture", "trend", NOW)
    version = StrategyVersion(
        uuid4(),
        strategy.id,
        "v1",
        "abc",
        "moving_average_trend",
        {"short_window": 2, "long_window": 3},
        NOW,
    )
    snapshot = DatasetSnapshot(
        uuid4(),
        "fixture",
        source.market,
        source.instrument,
        source.timeframe,
        bars[0].timestamp,
        bars[-1].timestamp,
        "ohlcv-v1",
        canonical_bars_checksum(bars),
        f"{uuid4()}/bars.parquet",
        AdjustmentPolicy.RAW,
        NOW,
    )
    experiment = Experiment(
        uuid4(),
        hypothesis.id,
        version.id,
        snapshot.id,
        ExperimentStatus.COMPLETED,
        NOW,
    )
    configuration = serialize_execution_configuration(
        BacktestConfiguration(
            Decimal("10000"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
        ),
        AnalyticsConfiguration(252),
    )
    run = ExperimentRun(
        uuid4(),
        experiment.id,
        "abc",
        "backtest-engine-v1",
        "zero-v1",
        "zero-v1",
        configuration,
        NOW,
        NOW,
        ExperimentRunStatus.COMPLETED,
    )
    gate = ValidationGateResult(
        uuid4(),
        run.id,
        version.id,
        "HISTORICAL_TO_PAPER",
        1,
        GateDecision.PASS,
        (),
        {},
        {},
        "validation-gate-v1",
        NOW,
        "gate-fp",
    )
    hypotheses.add(hypothesis)
    strategies.add(strategy)
    strategies.add_version(version)
    datasets.add(snapshot)
    experiments.add(experiment)
    experiments.add_run(run)
    gates.add(gate)
    promotion = PaperPromotionService(
        promotions, experiments, gates, strategies, datasets, lambda _: source
    ).approve(
        run.id,
        gate.id,
        confirm=True,
        reason="integration forward-only approval",
        actor="test-operator",
    )
    session = PaperSession(
        uuid4(),
        source.market,
        source.instrument,
        source.timeframe,
        source.adjustment_policy,
        "replay",
        "replay-provider-v1",
        snapshot.id,
        snapshot.checksum,
        bars[0].timestamp,
        (),
        PaperSessionStatus.CREATED,
        None,
        None,
        None,
        None,
        NOW,
    )
    papers.add_session(session)
    participant = AddPaperParticipant(
        papers, promotions, experiments, strategies
    ).execute(session.id, promotion.id)
    PaperLifecycle(papers, clock=lambda: NOW).start_session(session.id)
    processor = ProcessPaperBar(papers, strategies)
    for item in bars[:3]:
        processor.execute(session.id, item)

    postgres_session.expire_all()
    restarted_papers = SQLAlchemyPaperRepository(postgres_session)
    restarted_processor = ProcessPaperBar(restarted_papers, strategies)
    for item in bars[3:]:
        restarted_processor.execute(session.id, item)
    duplicate = restarted_processor.execute(session.id, bars[-1])

    assert duplicate.duplicate
    assert len(restarted_papers.list_observations(session.id)) == len(bars)
    snapshots = restarted_papers.list_snapshots(participant.id)
    assert len(snapshots) == len(bars)
    assert snapshots[-1].processed_bar_count == len(bars)
    backtest = cast(dict[str, object], snapshots[-1].material_result["backtest"])
    assert backtest["final_equity"] == "8750"
