"""Track Alpaca PAPER order identity and reconciliation snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260825_0009"
down_revision: str | None = "20260819_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alpaca_paper_orders",
        sa.Column("order_id", sa.String(100), primary_key=True),
        sa.Column("client_order_id", sa.String(128), nullable=False, unique=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("order_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_alpaca_paper_orders_client_order_id",
        "alpaca_paper_orders",
        ["client_order_id"],
        unique=True,
    )
    op.create_index("ix_alpaca_paper_orders_symbol", "alpaca_paper_orders", ["symbol"])
    op.create_index("ix_alpaca_paper_orders_status", "alpaca_paper_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_alpaca_paper_orders_status", table_name="alpaca_paper_orders")
    op.drop_index("ix_alpaca_paper_orders_symbol", table_name="alpaca_paper_orders")
    op.drop_index(
        "ix_alpaca_paper_orders_client_order_id", table_name="alpaca_paper_orders"
    )
    op.drop_table("alpaca_paper_orders")
