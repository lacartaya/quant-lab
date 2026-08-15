"""Add append-only contextual research memory."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0007"
down_revision: str | None = "20260815_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "hypothesis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hypotheses.id"),
            nullable=False,
        ),
        sa.Column(
            "derived_from_hypothesis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hypotheses.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("strategy_family", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=100), nullable=False),
        sa.Column("instrument", sa.String(length=100), nullable=False),
        sa.Column("timeframe", sa.String(length=50), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("execution_model", sa.String(length=100), nullable=True),
        sa.Column("cost_model", sa.String(length=100), nullable=True),
        sa.Column("regime_scope", sa.String(length=100), nullable=True),
        sa.Column("tested_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tested_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reconsideration_conditions", postgresql.JSONB(), nullable=False),
        sa.Column("reconsideration_rationale", sa.Text(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("research_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "hypothesis_id",
        "derived_from_hypothesis_id",
        "status",
        "strategy_family",
        "market",
        "instrument",
        "timeframe",
        "research_fingerprint",
    ):
        op.create_index(f"ix_knowledge_records_{column}", "knowledge_records", [column])


def downgrade() -> None:
    for column in reversed(
        (
            "hypothesis_id",
            "derived_from_hypothesis_id",
            "status",
            "strategy_family",
            "market",
            "instrument",
            "timeframe",
            "research_fingerprint",
        )
    ):
        op.drop_index(f"ix_knowledge_records_{column}", table_name="knowledge_records")
    op.drop_table("knowledge_records")
