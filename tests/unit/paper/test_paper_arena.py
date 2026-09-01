# mypy: disable-error-code="no-untyped-def,var-annotated,arg-type"

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from infra.market_data import ReplayMarketDataProvider
from quant.analytics import AnalyticsConfiguration
from quant.application import (
    AddPaperParticipant,
    PaperEligibilityError,
    PaperObservationConflict,
    PaperOutOfOrderObservation,
    ProcessPaperBar,
)
from quant.application.dataset_snapshots import canonical_bars_checksum
from quant.application.experiments.evidence import backtest_material
from quant.application.experiments.registry import serialize_execution_configuration
from quant.backtest import (
    BacktestConfiguration,
    BacktestEngine,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import (
    AdjustmentPolicy,
    ExperimentRun,
    ExperimentRunStatus,
    GateDecision,
    HistoricalDataset,
    MarketBar,
    PaperParticipant,
    PaperParticipantStatus,
    PaperPromotion,
    PaperPromotionStatus,
    PaperSession,
    PaperSessionStatus,
    StrategyVersion,
    ValidationGateResult,
)
from quant.strategies import MovingAverageParameters, MovingAverageTrendStrategy

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def bar(day: int, close: str) -> MarketBar:
    timestamp = NOW + timedelta(days=day)
    price = Decimal(close)
    return MarketBar(timestamp, price, price, price, price, Decimal("100"))


def dataset() -> HistoricalDataset:
    return HistoricalDataset.from_bars(
        market="US_EQUITIES",
        instrument="SPY",
        timeframe="1D",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=(
            bar(0, "10"),
            bar(1, "11"),
            bar(2, "12"),
            bar(3, "8"),
            bar(4, "7"),
        ),
    )


class MemoryPaperRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, PaperSession] = {}
        self.participants: dict[UUID, PaperParticipant] = {}
        self.observations = []
        self.snapshots = []

    def add_session(self, value: PaperSession) -> None:
        self.sessions[value.id] = value

    save_session = add_session

    def get_session(self, value: UUID) -> PaperSession | None:
        return self.sessions.get(value)

    def list_sessions(self):
        return tuple(self.sessions.values())

    def add_participant(self, value: PaperParticipant) -> None:
        self.participants[value.id] = value

    save_participant = add_participant

    def get_participant(self, value: UUID) -> PaperParticipant | None:
        return self.participants.get(value)

    def list_participants(self, session_id: UUID):
        return tuple(
            x for x in self.participants.values() if x.session_id == session_id
        )

    def add_observation(self, value) -> None:
        self.observations.append(value)

    def get_observation(self, session_id: UUID, timestamp: datetime):
        return next(
            (
                x
                for x in self.observations
                if x.session_id == session_id and x.bar.timestamp == timestamp
            ),
            None,
        )

    def list_observations(self, session_id: UUID):
        return tuple(x for x in self.observations if x.session_id == session_id)

    def add_snapshot(self, value) -> None:
        self.snapshots.append(value)

    def latest_snapshot(self, participant_id: UUID):
        matches = [x for x in self.snapshots if x.participant_id == participant_id]
        return matches[-1] if matches else None

    def list_snapshots(self, participant_id: UUID):
        return tuple(x for x in self.snapshots if x.participant_id == participant_id)


class GetRepository:
    def __init__(self, value) -> None:
        if isinstance(value, ValidationGateResult):
            revoked = value.decision is GateDecision.FAIL
            value = PaperPromotion(
                value.id,
                uuid4(),
                value.strategy_version_id,
                uuid4(),
                value.experiment_run_id,
                value.id,
                uuid4(),
                value.policy_id,
                value.policy_version,
                value.decision.value,
                PaperPromotionStatus.REVOKED
                if revoked
                else PaperPromotionStatus.APPROVED,
                "test approval",
                "test-operator",
                NOW,
                NOW,
                NOW,
                NOW if revoked else None,
                "test-operator" if revoked else None,
                "gate failed fixture" if revoked else None,
            )
        self.value = value

    def get(self, identity: UUID):
        return self.value if self.value.id == identity else None


class StrategyRepository(GetRepository):
    def get_version(self, identity: UUID):
        return self.get(identity)


class ExperimentRepository:
    def __init__(self, run: ExperimentRun) -> None:
        self.run = run

    def get_run(self, identity: UUID):
        return self.run if self.run.id == identity else None


def paper_fixture(decision: GateDecision = GateDecision.PASS):
    papers = MemoryPaperRepository()
    version = StrategyVersion(
        uuid4(),
        uuid4(),
        "v1",
        "abc",
        "moving_average_trend",
        {"short_window": 2, "long_window": 3},
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
        uuid4(),
        "abc",
        "backtest-engine-v1",
        "zero-fee-v1",
        "zero-slippage-v1",
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
        decision,
        (),
        {},
        {},
        "validation-gate-v1",
        NOW,
        "fingerprint",
    )
    source = dataset()
    session = PaperSession(
        uuid4(),
        source.market,
        source.instrument,
        source.timeframe,
        source.adjustment_policy,
        "replay",
        "replay-provider-v1",
        uuid4(),
        canonical_bars_checksum(source.bars),
        source.bars[0].timestamp,
        (),
        PaperSessionStatus.RUNNING,
        NOW,
        None,
        None,
        None,
        NOW,
    )
    papers.add_session(session)
    return papers, version, run, gate, session, source


def test_replay_provider_is_forward_only() -> None:
    provider = ReplayMarketDataProvider(dataset())
    observed = []
    while (next_bar := provider.next_bar()) is not None:
        observed.append(next_bar.timestamp)

    assert observed == sorted(observed)
    assert len(observed) == 5
    assert provider.next_bar() is None


def test_gate_admission_requires_exact_passing_policy() -> None:
    papers, version, run, gate, session, _ = paper_fixture(GateDecision.FAIL)
    service = AddPaperParticipant(
        papers,
        GetRepository(gate),
        ExperimentRepository(run),
        StrategyRepository(version),
    )
    with pytest.raises(PaperEligibilityError):
        service.execute(session.id, gate.id)

    passing = replace(gate, decision=GateDecision.PASS)
    admitted = AddPaperParticipant(
        papers,
        GetRepository(passing),
        ExperimentRepository(run),
        StrategyRepository(version),
    ).execute(session.id, passing.id)
    assert admitted.strategy_version_id == version.id
    assert admitted.source_gate_evaluation_id == passing.id
    assert admitted.status is PaperParticipantStatus.ACTIVE
    with pytest.raises(PaperEligibilityError, match="strategy version"):
        service = AddPaperParticipant(
            papers,
            GetRepository(passing),
            ExperimentRepository(run),
            StrategyRepository(version),
        )
        service.execute(session.id, passing.id, strategy_version_id=uuid4())
    with pytest.raises(PaperEligibilityError, match="broker target"):
        service.execute(session.id, passing.id, broker_target="LIVE")


def test_operator_run_wrapped_execution_is_persisted_as_paper_configuration() -> None:
    papers, version, run, gate, session, _ = paper_fixture()
    wrapped = replace(
        run,
        configuration={
            "execution": dict(run.configuration),
            "evidence": {},
            "fingerprint": "sha256:test",
        },
    )
    participant = AddPaperParticipant(
        papers,
        GetRepository(gate),
        ExperimentRepository(wrapped),
        StrategyRepository(version),
    ).execute(session.id, gate.id)
    assert "engine_version" in participant.execution_configuration
    assert "execution" not in participant.execution_configuration


def test_processing_is_idempotent_and_rejects_conflicts_and_out_of_order() -> None:
    papers, version, run, gate, session, source = paper_fixture()
    participant = AddPaperParticipant(
        papers,
        GetRepository(gate),
        ExperimentRepository(run),
        StrategyRepository(version),
    ).execute(session.id, gate.id)
    processor = ProcessPaperBar(papers, StrategyRepository(version))

    first = processor.execute(session.id, source.bars[1])
    duplicate = processor.execute(session.id, source.bars[1])
    assert not first.duplicate and duplicate.duplicate
    assert len(papers.list_snapshots(participant.id)) == 1
    conflicting = replace(source.bars[1], close=Decimal("99"), high=Decimal("99"))
    with pytest.raises(PaperObservationConflict):
        processor.execute(session.id, conflicting)
    with pytest.raises(PaperOutOfOrderObservation):
        processor.execute(session.id, source.bars[0])


def test_forward_replay_preserves_next_bar_timing_and_independent_portfolios() -> None:
    papers, version, run, gate, session, source = paper_fixture()
    service = AddPaperParticipant(
        papers,
        GetRepository(gate),
        ExperimentRepository(run),
        StrategyRepository(version),
    )
    first = service.execute(session.id, gate.id)
    second_gate = replace(gate, id=uuid4())
    second = AddPaperParticipant(
        papers,
        GetRepository(second_gate),
        ExperimentRepository(run),
        StrategyRepository(version),
    ).execute(session.id, second_gate.id)
    processor = ProcessPaperBar(papers, StrategyRepository(version))
    for item in source.bars:
        processor.execute(session.id, item)

    first_result = papers.latest_snapshot(first.id).material_result["backtest"]
    second_result = papers.latest_snapshot(second.id).material_result["backtest"]
    assert first_result == second_result
    orders = first_result["orders"]
    fills = first_result["fills"]
    assert orders[0]["timestamp"].startswith(source.bars[3].timestamp.isoformat()[:19])
    assert fills[0]["timestamp"].startswith(source.bars[3].timestamp.isoformat()[:19])
    assert len(papers.list_snapshots(first.id)) == len(source.bars)
    assert len(papers.list_snapshots(second.id)) == len(source.bars)
    historical = BacktestEngine().run(
        source,
        MovingAverageTrendStrategy(MovingAverageParameters(2, 3)),
        BacktestConfiguration(
            Decimal("10000"), Decimal("1"), ZeroFeeModel(), ZeroSlippageModel()
        ),
        evaluation_start=source.bars[0].timestamp,
    )
    assert first_result == backtest_material(historical)


def test_restart_continuation_matches_uninterrupted_replay() -> None:
    papers, version, run, gate, session, source = paper_fixture()
    participant = AddPaperParticipant(
        papers,
        GetRepository(gate),
        ExperimentRepository(run),
        StrategyRepository(version),
    ).execute(session.id, gate.id)
    processor = ProcessPaperBar(papers, StrategyRepository(version))
    for item in source.bars[:3]:
        processor.execute(session.id, item)

    restarted = MemoryPaperRepository()
    restarted.sessions = dict(papers.sessions)
    restarted.participants = dict(papers.participants)
    restarted.observations = list(papers.observations)
    restarted.snapshots = list(papers.snapshots)
    restarted_processor = ProcessPaperBar(restarted, StrategyRepository(version))
    for item in source.bars[3:]:
        restarted_processor.execute(session.id, item)

    uninterrupted, version2, run2, gate2, session2, source2 = paper_fixture()
    # Keep lineage/configuration equal so only processing continuity is compared.
    version2 = replace(version2, id=version.id)
    run2 = replace(run2, id=run.id)
    gate2 = replace(
        gate2,
        experiment_run_id=run.id,
        strategy_version_id=version.id,
    )
    baseline = AddPaperParticipant(
        uninterrupted,
        GetRepository(gate2),
        ExperimentRepository(run2),
        StrategyRepository(version2),
    ).execute(session2.id, gate2.id)
    baseline_processor = ProcessPaperBar(uninterrupted, StrategyRepository(version2))
    for item in source2.bars:
        baseline_processor.execute(session2.id, item)

    restarted_result = restarted.latest_snapshot(participant.id)
    baseline_result = uninterrupted.latest_snapshot(baseline.id)
    assert (
        restarted_result.material_result["backtest"]
        == baseline_result.material_result["backtest"]
    )
    assert restarted_result.metrics == baseline_result.metrics
    assert len(restarted.list_observations(session.id)) == len(source.bars)
