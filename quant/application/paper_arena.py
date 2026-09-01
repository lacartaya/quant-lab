from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from quant.analytics import analyze_backtest
from quant.application.dataset_snapshots import canonical_bars_checksum
from quant.application.experiments.evidence import (
    backtest_material,
    canonical_value,
    evidence_fingerprint,
)
from quant.application.experiments.registry import (
    build_strategy,
    reconstruct_configurations,
)
from quant.backtest import BacktestEngine
from quant.domain import HistoricalDataset, MarketBar, PaperPromotionStatus
from quant.domain.paper import (
    PaperObservation,
    PaperParticipant,
    PaperParticipantComparison,
    PaperParticipantStatus,
    PaperSession,
    PaperSessionStatus,
    PaperSnapshot,
)
from quant.ports import (
    DatasetRepository,
    ExperimentRepository,
    PaperPromotionRepository,
    StrategyRepository,
)
from quant.ports.live_market_data import LiveMarketDataProvider
from quant.ports.paper_repository import PaperRepository

PAPER_ENGINE_VERSION = "paper-engine-v1"
REPLAY_PROVIDER_VERSION = "replay-provider-v1"
ALPACA_IEX_PROVIDER_VERSION = "alpaca-iex-polling-v1"
HISTORICAL_TO_PAPER_POLICY = "HISTORICAL_TO_PAPER"


class PaperArenaError(RuntimeError):
    pass


class PaperEligibilityError(PaperArenaError):
    pass


class PaperObservationConflict(PaperArenaError):
    pass


class PaperOutOfOrderObservation(PaperArenaError):
    pass


@dataclass(frozen=True, slots=True)
class PaperProcessingResult:
    session: PaperSession
    observation: PaperObservation | None
    snapshots: tuple[PaperSnapshot, ...]
    duplicate: bool
    completed: bool


@dataclass(frozen=True, slots=True)
class CreatePaperSession:
    datasets: DatasetRepository
    load_dataset: Callable[[UUID], HistoricalDataset]
    papers: PaperRepository
    id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def execute(
        self,
        dataset_snapshot_id: UUID,
        evaluation_start: datetime,
        provider_name: str = "replay",
    ) -> PaperSession:
        if evaluation_start.tzinfo is None or evaluation_start.utcoffset() is None:
            raise ValueError("paper evaluation start must include a timezone")
        evaluation_start = evaluation_start.astimezone(UTC)
        snapshot = self.datasets.get(dataset_snapshot_id)
        if snapshot is None:
            raise LookupError(f"dataset snapshot {dataset_snapshot_id} was not found")
        dataset = self.load_dataset(dataset_snapshot_id)
        if provider_name not in {"replay", "alpaca_iex"}:
            raise ValueError("paper provider must be replay or alpaca_iex")
        if provider_name == "alpaca_iex" and snapshot.timeframe not in {
            "1Min",
            "1Minute",
        }:
            raise ValueError(
                "Alpaca IEX forward polling requires a one-minute warm-up snapshot"
            )
        if provider_name == "replay" and not any(
            bar.timestamp >= evaluation_start for bar in dataset.bars
        ):
            raise ValueError("paper evaluation start is outside the replay dataset")
        session = PaperSession(
            id=self.id_factory(),
            market=snapshot.market,
            instrument=snapshot.instrument,
            timeframe=snapshot.timeframe,
            adjustment_policy=snapshot.adjustment_policy,
            provider_name=provider_name,
            provider_version=(
                REPLAY_PROVIDER_VERSION
                if provider_name == "replay"
                else ALPACA_IEX_PROVIDER_VERSION
            ),
            dataset_snapshot_id=snapshot.id,
            dataset_checksum=snapshot.checksum,
            evaluation_start=evaluation_start,
            warmup_bars=tuple(
                bar for bar in dataset.bars if bar.timestamp < evaluation_start
            ),
            status=PaperSessionStatus.CREATED,
            started_at=None,
            completed_at=None,
            last_processed_at=None,
            last_error=None,
            created_at=self.clock(),
        )
        self.papers.add_session(session)
        return session


@dataclass(frozen=True, slots=True)
class AddPaperParticipant:
    papers: PaperRepository
    promotions: PaperPromotionRepository
    experiments: ExperimentRepository
    strategies: StrategyRepository
    id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def execute(
        self,
        session_id: UUID,
        paper_promotion_id: UUID,
        *,
        strategy_version_id: UUID | None = None,
        broker_target: str | None = None,
    ) -> PaperParticipant:
        session = _required(
            self.papers.get_session(session_id), "paper session", session_id
        )
        if session.status in {PaperSessionStatus.COMPLETED, PaperSessionStatus.FAILED}:
            raise PaperArenaError(
                "cannot add a participant to a terminal paper session"
            )
        if broker_target is not None:
            raise PaperEligibilityError("Paper Arena does not accept a broker target")
        promotion = _required(
            self.promotions.get(paper_promotion_id),
            "paper promotion",
            paper_promotion_id,
        )
        if promotion.status is not PaperPromotionStatus.APPROVED:
            raise PaperEligibilityError(
                "paper admission requires an approved, non-revoked Paper promotion"
            )
        if (
            strategy_version_id is not None
            and strategy_version_id != promotion.strategy_version_id
        ):
            raise PaperEligibilityError(
                "strategy version does not match promoted lineage"
            )
        version = _required(
            self.strategies.get_version(promotion.strategy_version_id),
            "strategy version",
            promotion.strategy_version_id,
        )
        build_strategy(version)
        run = _required(
            self.experiments.get_run(promotion.experiment_run_id),
            "experiment run",
            promotion.experiment_run_id,
        )
        execution_configuration: Mapping[str, object] = run.configuration
        nested_execution = run.configuration.get("execution")
        if isinstance(nested_execution, Mapping):
            execution_configuration = nested_execution
        backtest, _ = reconstruct_configurations(execution_configuration)
        participant = PaperParticipant(
            id=self.id_factory(),
            session_id=session.id,
            strategy_version_id=version.id,
            source_gate_evaluation_id=promotion.validation_gate_id,
            status=PaperParticipantStatus.ACTIVE
            if session.status is PaperSessionStatus.RUNNING
            else PaperParticipantStatus.PENDING,
            initial_capital=backtest.initial_cash,
            execution_configuration=execution_configuration,
            paper_engine_version=PAPER_ENGINE_VERSION,
            started_at=self.clock()
            if session.status is PaperSessionStatus.RUNNING
            else None,
            stopped_at=None,
            last_processed_at=None,
            last_successful_at=None,
            last_error=None,
            created_at=self.clock(),
            paper_promotion_id=promotion.id,
        )
        self.papers.add_participant(participant)
        return participant


@dataclass(frozen=True, slots=True)
class PaperLifecycle:
    papers: PaperRepository
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def start_session(self, session_id: UUID) -> PaperSession:
        session = _required(
            self.papers.get_session(session_id), "paper session", session_id
        )
        if session.status not in {
            PaperSessionStatus.CREATED,
            PaperSessionStatus.PAUSED,
        }:
            raise PaperArenaError(
                "paper session cannot be started from its current status"
            )
        now = self.clock()
        updated = replace(
            session,
            status=PaperSessionStatus.RUNNING,
            started_at=session.started_at or now,
            last_error=None,
        )
        self.papers.save_session(updated)
        for participant in self.papers.list_participants(session_id):
            if participant.status in {
                PaperParticipantStatus.PENDING,
                PaperParticipantStatus.PAUSED,
            }:
                self.papers.save_participant(
                    replace(
                        participant,
                        status=PaperParticipantStatus.ACTIVE,
                        started_at=participant.started_at or now,
                        last_error=None,
                    )
                )
        return updated

    def pause_session(self, session_id: UUID) -> PaperSession:
        session = _required(
            self.papers.get_session(session_id), "paper session", session_id
        )
        if session.status is not PaperSessionStatus.RUNNING:
            raise PaperArenaError("only a running paper session can be paused")
        updated = replace(session, status=PaperSessionStatus.PAUSED)
        self.papers.save_session(updated)
        for participant in self.papers.list_participants(session_id):
            if participant.status is PaperParticipantStatus.ACTIVE:
                self.papers.save_participant(
                    replace(participant, status=PaperParticipantStatus.PAUSED)
                )
        return updated

    def pause_participant(self, participant_id: UUID) -> PaperParticipant:
        participant = _required(
            self.papers.get_participant(participant_id),
            "paper participant",
            participant_id,
        )
        if participant.status is not PaperParticipantStatus.ACTIVE:
            raise PaperArenaError("only an active participant can be paused")
        updated = replace(participant, status=PaperParticipantStatus.PAUSED)
        self.papers.save_participant(updated)
        return updated

    def stop_participant(self, participant_id: UUID) -> PaperParticipant:
        participant = _required(
            self.papers.get_participant(participant_id),
            "paper participant",
            participant_id,
        )
        if participant.status is PaperParticipantStatus.STOPPED:
            return participant
        updated = replace(
            participant, status=PaperParticipantStatus.STOPPED, stopped_at=self.clock()
        )
        self.papers.save_participant(updated)
        return updated


@dataclass(frozen=True, slots=True)
class ProcessPaperBar:
    papers: PaperRepository
    strategies: StrategyRepository
    id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def execute(self, session_id: UUID, bar: MarketBar) -> PaperProcessingResult:
        session = _required(
            self.papers.get_session(session_id), "paper session", session_id
        )
        if session.status is not PaperSessionStatus.RUNNING:
            raise PaperArenaError("paper session is not running")
        _validate_bar_domain(session, bar)
        checksum = canonical_bars_checksum((bar,))
        existing = self.papers.get_observation(session.id, bar.timestamp)
        if existing is not None:
            if existing.content_checksum != checksum:
                raise PaperObservationConflict(
                    "paper observation identity has conflicting content"
                )
            return PaperProcessingResult(session, existing, (), True, False)
        if (
            session.last_processed_at is not None
            and bar.timestamp < session.last_processed_at
        ):
            raise PaperOutOfOrderObservation(
                "paper observation is older than the last processed bar"
            )
        if bar.timestamp < session.evaluation_start:
            raise PaperOutOfOrderObservation(
                "paper observation precedes the evaluation boundary"
            )
        now = self.clock()
        observation = PaperObservation(
            self.id_factory(), session.id, bar, checksum, now
        )
        self.papers.add_observation(observation)
        observations = (*self.papers.list_observations(session.id),)
        snapshots: list[PaperSnapshot] = []
        for participant in self.papers.list_participants(session.id):
            if participant.status is not PaperParticipantStatus.ACTIVE:
                continue
            snapshots.append(
                self._process_participant(
                    session, participant, observation, observations, now
                )
            )
        updated_session = replace(
            session, last_processed_at=bar.timestamp, last_error=None
        )
        self.papers.save_session(updated_session)
        return PaperProcessingResult(
            updated_session, observation, tuple(snapshots), False, False
        )

    def _process_participant(
        self,
        session: PaperSession,
        participant: PaperParticipant,
        observation: PaperObservation,
        observations: tuple[PaperObservation, ...],
        now: datetime,
    ) -> PaperSnapshot:
        version = _required(
            self.strategies.get_version(participant.strategy_version_id),
            "strategy version",
            participant.strategy_version_id,
        )
        strategy = build_strategy(version)
        backtest_configuration, analytics_configuration = reconstruct_configurations(
            participant.execution_configuration
        )
        bars = (*session.warmup_bars, *(item.bar for item in observations))
        dataset = HistoricalDataset.from_bars(
            market=session.market,
            instrument=session.instrument,
            timeframe=session.timeframe,
            adjustment_policy=session.adjustment_policy,
            bars=bars,
            metadata={
                "paper_session_id": str(session.id),
                "provider_version": session.provider_version,
            },
        )
        result = BacktestEngine().run(
            dataset,
            strategy,
            backtest_configuration,
            evaluation_start=session.evaluation_start,
        )
        metrics = analyze_backtest(result, analytics_configuration)
        material = {
            "paper_engine_version": PAPER_ENGINE_VERSION,
            "paper_session_id": str(session.id),
            "paper_participant_id": str(participant.id),
            "strategy_version_id": str(version.id),
            "source_gate_evaluation_id": str(participant.source_gate_evaluation_id),
            "paper_promotion_id": str(participant.paper_promotion_id),
            "provider": {
                "name": session.provider_name,
                "version": session.provider_version,
            },
            "dataset_snapshot_id": str(session.dataset_snapshot_id),
            "dataset_checksum": session.dataset_checksum,
            "evaluation_start": canonical_value(session.evaluation_start),
            "execution_configuration": canonical_value(
                participant.execution_configuration
            ),
            "processed_observations": [
                canonical_value(item.bar) for item in observations
            ],
            "signals": canonical_value(result.signals),
            "skipped_signals": canonical_value(result.skipped_signals),
            "unexecuted_signals": canonical_value(result.unexecuted_signals),
            "backtest": backtest_material(result),
            "metrics": canonical_value(metrics),
            "execution_context": "paper_simulated",
        }
        snapshot = PaperSnapshot(
            self.id_factory(),
            participant.id,
            observation.id,
            observation.bar.timestamp,
            len(observations),
            material,
            metrics,
            evidence_fingerprint(material),
            now,
        )
        self.papers.add_snapshot(snapshot)
        self.papers.save_participant(
            replace(
                participant,
                last_processed_at=observation.bar.timestamp,
                last_successful_at=now,
                last_error=None,
            )
        )
        return snapshot


@dataclass(frozen=True, slots=True)
class AdvanceReplaySession:
    papers: PaperRepository
    load_dataset: Callable[[UUID], HistoricalDataset]
    processor: ProcessPaperBar
    provider_factory: Callable[
        [HistoricalDataset, datetime | None], LiveMarketDataProvider
    ]
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def execute(self, session_id: UUID) -> PaperProcessingResult:
        session = _required(
            self.papers.get_session(session_id), "paper session", session_id
        )
        if session.provider_name != "replay":
            raise PaperArenaError("session does not use the replay provider")
        dataset = self.load_dataset(session.dataset_snapshot_id)
        eligible = tuple(
            bar
            for bar in dataset.bars
            if bar.timestamp >= session.evaluation_start
            and (
                session.last_processed_at is None
                or bar.timestamp > session.last_processed_at
            )
        )
        if not eligible:
            completed = replace(
                session, status=PaperSessionStatus.COMPLETED, completed_at=self.clock()
            )
            self.papers.save_session(completed)
            return PaperProcessingResult(completed, None, (), False, True)
        forward = HistoricalDataset.from_bars(
            market=dataset.market,
            instrument=dataset.instrument,
            timeframe=dataset.timeframe,
            adjustment_policy=dataset.adjustment_policy,
            bars=eligible,
            metadata=dataset.metadata,
        )
        provider = self.provider_factory(forward, session.last_processed_at)
        bar = provider.next_bar()
        if bar is not None:
            return self.processor.execute(session_id, bar)
        completed = replace(
            session, status=PaperSessionStatus.COMPLETED, completed_at=self.clock()
        )
        self.papers.save_session(completed)
        return PaperProcessingResult(completed, None, (), False, True)


@dataclass(frozen=True, slots=True)
class AdvanceLiveSession:
    papers: PaperRepository
    processor: ProcessPaperBar

    def execute(
        self, session_id: UUID, provider: LiveMarketDataProvider
    ) -> PaperProcessingResult:
        session = _required(
            self.papers.get_session(session_id), "paper session", session_id
        )
        if session.provider_name != provider.name:
            raise PaperArenaError("session and live provider identities do not match")
        bar = provider.next_bar()
        if bar is None:
            return PaperProcessingResult(session, None, (), False, False)
        return self.processor.execute(session_id, bar)


@dataclass(frozen=True, slots=True)
class ComparePaperParticipants:
    papers: PaperRepository

    def execute(self, session_id: UUID) -> tuple[PaperParticipantComparison, ...]:
        comparisons: list[PaperParticipantComparison] = []
        for participant in self.papers.list_participants(session_id):
            snapshot = self.papers.latest_snapshot(participant.id)
            equity = None
            if snapshot is not None:
                backtest = snapshot.material_result.get("backtest")
                if isinstance(backtest, dict) and isinstance(
                    backtest.get("final_equity"), str
                ):
                    equity = Decimal(backtest["final_equity"])
            comparisons.append(
                PaperParticipantComparison(
                    participant.id,
                    participant.strategy_version_id,
                    participant.status,
                    snapshot.processed_bar_count if snapshot else 0,
                    snapshot.metrics if snapshot else None,
                    equity,
                )
            )
        return tuple(comparisons)


def _validate_bar_domain(session: PaperSession, bar: MarketBar) -> None:
    del bar
    # MarketBar intentionally carries no duplicated symbol fields; session/feed
    # construction owns and validates market, instrument, and timeframe identity.


def _required[ValueT](value: ValueT | None, kind: str, identity: UUID) -> ValueT:
    if value is None:
        raise LookupError(f"{kind} {identity} was not found")
    return value
