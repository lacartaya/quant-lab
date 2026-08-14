"""Add immutable dataset storage metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0002"
down_revision: str | None = "20260815_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dataset_snapshots",
        sa.Column("storage_location", sa.Text(), nullable=False),
    )
    op.add_column(
        "dataset_snapshots",
        sa.Column("adjustment_policy", sa.String(16), nullable=False),
    )
    op.create_check_constraint(
        "ck_dataset_snapshots_adjustment_policy",
        "dataset_snapshots",
        "adjustment_policy IN ('raw', 'adjusted')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_dataset_snapshots_adjustment_policy",
        "dataset_snapshots",
        type_="check",
    )
    op.drop_column("dataset_snapshots", "adjustment_policy")
    op.drop_column("dataset_snapshots", "storage_location")
