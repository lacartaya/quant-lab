"""Allow parameter-sensitivity validation evidence."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260815_0004"
down_revision: str | None = "20260815_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_validation_runs_type", "validation_runs", type_="check"
    )
    op.create_check_constraint(
        "ck_validation_runs_type",
        "validation_runs",
        "validation_type IN ('backtest', 'out_of_sample', 'walk_forward', "
        "'stress', 'monte_carlo', 'parameter_sensitivity')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_validation_runs_type", "validation_runs", type_="check"
    )
    op.create_check_constraint(
        "ck_validation_runs_type",
        "validation_runs",
        "validation_type IN ('backtest', 'out_of_sample', 'walk_forward', "
        "'stress', 'monte_carlo')",
    )
