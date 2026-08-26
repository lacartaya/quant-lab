from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class HypothesisModel(Base):
    __tablename__ = "hypotheses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('known_replicated', 'active_research', "
            "'validated_internal', 'rejected', 'retired')",
            name="ck_hypotheses_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    strategy_family: Mapped[str] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(100))
    timeframe: Mapped[str] = mapped_column(String(50))
    expected_benefit: Mapped[str] = mapped_column(Text)
    expected_tradeoff: Mapped[str] = mapped_column(Text)
    success_criteria: Mapped[str] = mapped_column(Text)
    rejection_criteria: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    reconsideration_conditions: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class KnowledgeRecordModel(Base):
    __tablename__ = "knowledge_records"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    hypothesis_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("hypotheses.id"), index=True
    )
    derived_from_hypothesis_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("hypotheses.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    strategy_family: Mapped[str] = mapped_column(String(100), index=True)
    market: Mapped[str] = mapped_column(String(100), index=True)
    instrument: Mapped[str] = mapped_column(String(100), index=True)
    timeframe: Mapped[str] = mapped_column(String(50), index=True)
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB)
    execution_model: Mapped[str | None] = mapped_column(String(100))
    cost_model: Mapped[str | None] = mapped_column(String(100))
    regime_scope: Mapped[str | None] = mapped_column(String(100))
    tested_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tested_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    reconsideration_conditions: Mapped[list[str]] = mapped_column(JSONB)
    reconsideration_rationale: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    research_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StrategyModel(Base):
    __tablename__ = "strategies"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    strategy_family: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StrategyVersionModel(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (
        UniqueConstraint("strategy_id", "version", name="uq_strategy_version"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    strategy_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("strategies.id"), index=True
    )
    version: Mapped[str] = mapped_column(String(100))
    git_commit: Mapped[str] = mapped_column(String(255))
    algorithm_key: Mapped[str] = mapped_column(String(100))
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DatasetSnapshotModel(Base):
    __tablename__ = "dataset_snapshots"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_dataset_snapshot_range"),
        CheckConstraint(
            "adjustment_policy IN ('raw', 'adjusted')",
            name="ck_dataset_snapshots_adjustment_policy",
        ),
        UniqueConstraint(
            "provider",
            "market",
            "instrument",
            "timeframe",
            "start_at",
            "end_at",
            "version",
            "checksum",
            name="uq_dataset_snapshot_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(100))
    instrument: Mapped[str] = mapped_column(String(100))
    timeframe: Mapped[str] = mapped_column(String(50))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[str] = mapped_column(String(100))
    checksum: Mapped[str] = mapped_column(String(255))
    storage_location: Mapped[str] = mapped_column(Text)
    adjustment_policy: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExperimentModel(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed', 'rejected')",
            name="ck_experiments_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    hypothesis_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("hypotheses.id"), index=True
    )
    strategy_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("strategy_versions.id"), index=True
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("dataset_snapshots.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExperimentRunModel(Base):
    __tablename__ = "experiment_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed')",
            name="ck_experiment_runs_status",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_experiment_run_completion",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    experiment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id"), index=True
    )
    git_commit: Mapped[str] = mapped_column(String(255))
    engine_version: Mapped[str] = mapped_column(String(100))
    fee_model_version: Mapped[str] = mapped_column(String(100))
    slippage_model_version: Mapped[str] = mapped_column(String(100))
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))


class ValidationRunModel(Base):
    __tablename__ = "validation_runs"
    __table_args__ = (
        CheckConstraint(
            "validation_type IN ('backtest', 'out_of_sample', 'walk_forward', "
            "'stress', 'monte_carlo', 'parameter_sensitivity', "
            "'adversarial_review')",
            name="ck_validation_runs_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'passed', 'failed')",
            name="ck_validation_runs_status",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_validation_run_completion",
        ),
        CheckConstraint(
            "trade_count IS NULL OR trade_count >= 0",
            name="ck_validation_run_trade_count",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    experiment_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("experiment_runs.id"), index=True
    )
    validation_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    has_metric_set: Mapped[bool] = mapped_column(Boolean)
    total_return: Mapped[float | None] = mapped_column(Float)
    cagr: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    volatility: Mapped[float | None] = mapped_column(Float)
    sharpe: Mapped[float | None] = mapped_column(Float)
    sortino: Mapped[float | None] = mapped_column(Float)
    calmar: Mapped[float | None] = mapped_column(Float)
    profit_factor: Mapped[float | None] = mapped_column(Float)
    win_rate: Mapped[float | None] = mapped_column(Float)
    expectancy: Mapped[float | None] = mapped_column(Float)
    trade_count: Mapped[int | None] = mapped_column(Integer)


class GateEvaluationModel(Base):
    __tablename__ = "gate_evaluations"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('pass', 'fail')", name="ck_gate_evaluations_decision"
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    experiment_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("experiment_runs.id"), index=True
    )
    strategy_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("strategy_versions.id"), index=True
    )
    policy_id: Mapped[str] = mapped_column(String(100), index=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16))
    rule_results: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    source_evidence: Mapped[dict[str, object]] = mapped_column(JSONB)
    policy: Mapped[dict[str, object]] = mapped_column(JSONB)
    evaluator_version: Mapped[str] = mapped_column(String(100))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fingerprint: Mapped[str] = mapped_column(String(100))


class PaperSessionModel(Base):
    __tablename__ = "paper_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'running', 'paused', 'completed', 'failed')",
            name="ck_paper_sessions_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    market: Mapped[str] = mapped_column(String(100), index=True)
    instrument: Mapped[str] = mapped_column(String(100), index=True)
    timeframe: Mapped[str] = mapped_column(String(50), index=True)
    adjustment_policy: Mapped[str] = mapped_column(String(16))
    provider_name: Mapped[str] = mapped_column(String(100))
    provider_version: Mapped[str] = mapped_column(String(100))
    dataset_snapshot_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("dataset_snapshots.id"), index=True
    )
    dataset_checksum: Mapped[str] = mapped_column(String(255))
    evaluation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    warmup_bars: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaperParticipantModel(Base):
    __tablename__ = "paper_participants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'paused', 'stopped')",
            name="ck_paper_participants_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("paper_sessions.id"), index=True
    )
    strategy_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("strategy_versions.id"), index=True
    )
    source_gate_evaluation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("gate_evaluations.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), index=True)
    initial_capital: Mapped[str] = mapped_column(String(100))
    execution_configuration: Mapped[dict[str, object]] = mapped_column(JSONB)
    paper_engine_version: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaperObservationModel(Base):
    __tablename__ = "paper_observations"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "timestamp", name="uq_paper_observation_identity"
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("paper_sessions.id"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bar: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_checksum: Mapped[str] = mapped_column(String(100))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaperSnapshotModel(Base):
    __tablename__ = "paper_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "participant_id", "observation_id", name="uq_paper_snapshot_observation"
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("paper_participants.id"), index=True
    )
    observation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("paper_observations.id"), index=True
    )
    observation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_bar_count: Mapped[int] = mapped_column(Integer)
    material_result: Mapped[dict[str, object]] = mapped_column(JSONB)
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB)
    fingerprint: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlpacaPaperOrderModel(Base):
    __tablename__ = "alpaca_paper_orders"

    order_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    order_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PromotionDecisionModel(Base):
    __tablename__ = "promotion_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('promote', 'reject', 'continue_testing', 'pause')",
            name="ck_promotion_decisions_decision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    experiment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
