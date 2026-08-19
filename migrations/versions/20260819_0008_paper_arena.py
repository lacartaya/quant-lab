"""Add persistent Paper Arena sessions, participants, observations, and snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260819_0008"
down_revision: str | None = "20260815_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market", sa.String(100), nullable=False),
        sa.Column("instrument", sa.String(100), nullable=False),
        sa.Column("timeframe", sa.String(50), nullable=False),
        sa.Column("adjustment_policy", sa.String(16), nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column("provider_version", sa.String(100), nullable=False),
        sa.Column(
            "dataset_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dataset_snapshots.id"),
            nullable=False,
        ),
        sa.Column("dataset_checksum", sa.String(255), nullable=False),
        sa.Column("evaluation_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warmup_bars", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_processed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('created', 'running', 'paused', 'completed', 'failed')",
            name="ck_paper_sessions_status",
        ),
    )
    for column in (
        "market",
        "instrument",
        "timeframe",
        "dataset_snapshot_id",
        "status",
    ):
        op.create_index(f"ix_paper_sessions_{column}", "paper_sessions", [column])
    op.create_table(
        "paper_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("paper_sessions.id"),
            nullable=False,
        ),
        sa.Column(
            "strategy_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategy_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "source_gate_evaluation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gate_evaluations.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("initial_capital", sa.String(100), nullable=False),
        sa.Column("execution_configuration", postgresql.JSONB(), nullable=False),
        sa.Column("paper_engine_version", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        sa.Column("last_processed_at", sa.DateTime(timezone=True)),
        sa.Column("last_successful_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'paused', 'stopped')",
            name="ck_paper_participants_status",
        ),
    )
    for column in (
        "session_id",
        "strategy_version_id",
        "source_gate_evaluation_id",
        "status",
    ):
        op.create_index(
            f"ix_paper_participants_{column}", "paper_participants", [column]
        )
    op.create_table(
        "paper_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("paper_sessions.id"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bar", postgresql.JSONB(), nullable=False),
        sa.Column("content_checksum", sa.String(100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id", "timestamp", name="uq_paper_observation_identity"
        ),
    )
    op.create_index(
        "ix_paper_observations_session_id", "paper_observations", ["session_id"]
    )
    op.create_table(
        "paper_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "participant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("paper_participants.id"),
            nullable=False,
        ),
        sa.Column(
            "observation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("paper_observations.id"),
            nullable=False,
        ),
        sa.Column("observation_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_bar_count", sa.Integer(), nullable=False),
        sa.Column("material_result", postgresql.JSONB(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("fingerprint", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "participant_id", "observation_id", name="uq_paper_snapshot_observation"
        ),
    )
    op.create_index(
        "ix_paper_snapshots_participant_id", "paper_snapshots", ["participant_id"]
    )
    op.create_index(
        "ix_paper_snapshots_observation_id", "paper_snapshots", ["observation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_paper_snapshots_observation_id", table_name="paper_snapshots")
    op.drop_index("ix_paper_snapshots_participant_id", table_name="paper_snapshots")
    op.drop_table("paper_snapshots")
    op.drop_index("ix_paper_observations_session_id", table_name="paper_observations")
    op.drop_table("paper_observations")
    for column in reversed(
        ("session_id", "strategy_version_id", "source_gate_evaluation_id", "status")
    ):
        op.drop_index(
            f"ix_paper_participants_{column}", table_name="paper_participants"
        )
    op.drop_table("paper_participants")
    for column in reversed(
        ("market", "instrument", "timeframe", "dataset_snapshot_id", "status")
    ):
        op.drop_index(f"ix_paper_sessions_{column}", table_name="paper_sessions")
    op.drop_table("paper_sessions")
