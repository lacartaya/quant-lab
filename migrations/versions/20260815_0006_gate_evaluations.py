"""Add immutable validation gate evaluations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0006"
down_revision: str | None = "20260815_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gate_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "strategy_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategy_versions.id"),
            nullable=False,
        ),
        sa.Column("policy_id", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("rule_results", postgresql.JSONB(), nullable=False),
        sa.Column("source_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column("evaluator_version", sa.String(length=100), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=100), nullable=False),
        sa.CheckConstraint(
            "decision IN ('pass', 'fail')", name="ck_gate_evaluations_decision"
        ),
    )
    op.create_index(
        "ix_gate_evaluations_experiment_run_id",
        "gate_evaluations",
        ["experiment_run_id"],
    )
    op.create_index(
        "ix_gate_evaluations_strategy_version_id",
        "gate_evaluations",
        ["strategy_version_id"],
    )
    op.create_index("ix_gate_evaluations_policy_id", "gate_evaluations", ["policy_id"])


def downgrade() -> None:
    op.drop_index("ix_gate_evaluations_policy_id", table_name="gate_evaluations")
    op.drop_index(
        "ix_gate_evaluations_strategy_version_id", table_name="gate_evaluations"
    )
    op.drop_index(
        "ix_gate_evaluations_experiment_run_id", table_name="gate_evaluations"
    )
    op.drop_table("gate_evaluations")
