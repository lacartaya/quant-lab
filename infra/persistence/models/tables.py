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
