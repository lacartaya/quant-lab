"""Add stable executable strategy algorithm identity."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0003"
down_revision: str | None = "20260815_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "strategy_versions",
        sa.Column(
            "algorithm_key",
            sa.String(100),
            nullable=False,
            server_default="unregistered",
        ),
    )
    op.alter_column("strategy_versions", "algorithm_key", server_default=None)


def downgrade() -> None:
    op.drop_column("strategy_versions", "algorithm_key")
