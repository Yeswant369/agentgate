"""eval runs: persisted metrics history

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "ran_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("mode", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=True),
        sa.Column("scenario_count", sa.BigInteger, nullable=False),
        sa.Column("metrics", sa.JSON, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("eval_runs")
