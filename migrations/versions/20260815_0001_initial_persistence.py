"""Create the initial research persistence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hypotheses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("strategy_family", sa.String(100), nullable=False),
        sa.Column("market", sa.String(100), nullable=False),
        sa.Column("timeframe", sa.String(50), nullable=False),
        sa.Column("expected_benefit", sa.Text(), nullable=False),
        sa.Column("expected_tradeoff", sa.Text(), nullable=False),
        sa.Column("success_criteria", sa.Text(), nullable=False),
        sa.Column("rejection_criteria", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reconsideration_conditions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('known_replicated', 'active_research', "
            "'validated_internal', 'rejected', 'retired')",
            name="ck_hypotheses_status",
        ),
    )
    op.create_index("ix_hypotheses_status", "hypotheses", ["status"])

    op.create_table(
        "strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("strategy_family", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "strategy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "strategy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategies.id"),
            nullable=False,
        ),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("git_commit", sa.String(255), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("strategy_id", "version", name="uq_strategy_version"),
    )
    op.create_index(
        "ix_strategy_versions_strategy_id", "strategy_versions", ["strategy_id"]
    )

    op.create_table(
        "dataset_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("market", sa.String(100), nullable=False),
        sa.Column("instrument", sa.String(100), nullable=False),
        sa.Column("timeframe", sa.String(50), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("checksum", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_at > start_at", name="ck_dataset_snapshot_range"),
        sa.UniqueConstraint(
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

    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "hypothesis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hypotheses.id"),
            nullable=False,
        ),
        sa.Column(
            "strategy_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategy_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "dataset_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dataset_snapshots.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed', 'rejected')",
            name="ck_experiments_status",
        ),
    )
    for column in ("hypothesis_id", "strategy_version_id", "dataset_snapshot_id"):
        op.create_index(f"ix_experiments_{column}", "experiments", [column])

    op.create_table(
        "experiment_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id"),
            nullable=False,
        ),
        sa.Column("git_commit", sa.String(255), nullable=False),
        sa.Column("engine_version", sa.String(100), nullable=False),
        sa.Column("fee_model_version", sa.String(100), nullable=False),
        sa.Column("slippage_model_version", sa.String(100), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed')",
            name="ck_experiment_runs_status",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_experiment_run_completion",
        ),
    )
    op.create_index(
        "ix_experiment_runs_experiment_id", "experiment_runs", ["experiment_id"]
    )

    op.create_table(
        "validation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment_runs.id"),
            nullable=False,
        ),
        sa.Column("validation_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("has_metric_set", sa.Boolean(), nullable=False),
        sa.Column("total_return", sa.Float(), nullable=True),
        sa.Column("cagr", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("volatility", sa.Float(), nullable=True),
        sa.Column("sharpe", sa.Float(), nullable=True),
        sa.Column("sortino", sa.Float(), nullable=True),
        sa.Column("calmar", sa.Float(), nullable=True),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("expectancy", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "validation_type IN ('backtest', 'out_of_sample', 'walk_forward', "
            "'stress', 'monte_carlo')",
            name="ck_validation_runs_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'passed', 'failed')",
            name="ck_validation_runs_status",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_validation_run_completion",
        ),
        sa.CheckConstraint(
            "trade_count IS NULL OR trade_count >= 0",
            name="ck_validation_run_trade_count",
        ),
    )
    op.create_index(
        "ix_validation_runs_experiment_run_id",
        "validation_runs",
        ["experiment_run_id"],
    )

    op.create_table(
        "promotion_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('promote', 'reject', 'continue_testing', 'pause')",
            name="ck_promotion_decisions_decision",
        ),
    )
    op.create_index(
        "ix_promotion_decisions_experiment_id",
        "promotion_decisions",
        ["experiment_id"],
    )


def downgrade() -> None:
    op.drop_table("promotion_decisions")
    op.drop_table("validation_runs")
    op.drop_table("experiment_runs")
    op.drop_table("experiments")
    op.drop_table("dataset_snapshots")
    op.drop_table("strategy_versions")
    op.drop_table("strategies")
    op.drop_table("hypotheses")
