"""Add explicit Paper promotion approval boundary.

Revision ID: 20260901_0010
Revises: 20260825_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_0010"
down_revision: str | None = "20260825_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_promotions",
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
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id"),
            nullable=False,
        ),
        sa.Column(
            "experiment_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "validation_gate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gate_evaluations.id"),
            nullable=False,
        ),
        sa.Column(
            "dataset_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dataset_snapshots.id"),
            nullable=False,
        ),
        sa.Column("gate_policy_id", sa.String(100), nullable=False),
        sa.Column("gate_policy_version", sa.Integer(), nullable=False),
        sa.Column("gate_decision", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("approval_actor", sa.String(100), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by", sa.String(100)),
        sa.Column("revocation_reason", sa.Text()),
        sa.CheckConstraint(
            "status IN ('approved', 'revoked')", name="ck_paper_promotions_status"
        ),
        sa.UniqueConstraint(
            "experiment_run_id",
            "strategy_version_id",
            "validation_gate_id",
            name="uq_paper_promotion_lineage",
        ),
    )
    for column in (
        "hypothesis_id",
        "strategy_version_id",
        "experiment_id",
        "experiment_run_id",
        "validation_gate_id",
        "dataset_snapshot_id",
        "status",
    ):
        op.create_index(f"ix_paper_promotions_{column}", "paper_promotions", [column])
    op.add_column(
        "paper_participants",
        sa.Column("paper_promotion_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_paper_participants_promotion",
        "paper_participants",
        "paper_promotions",
        ["paper_promotion_id"],
        ["id"],
    )
    op.create_index(
        "ix_paper_participants_paper_promotion_id",
        "paper_participants",
        ["paper_promotion_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_participants_paper_promotion_id", table_name="paper_participants"
    )
    op.drop_constraint(
        "fk_paper_participants_promotion", "paper_participants", type_="foreignkey"
    )
    op.drop_column("paper_participants", "paper_promotion_id")
    op.drop_table("paper_promotions")
