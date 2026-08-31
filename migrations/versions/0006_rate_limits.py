"""rate limits: DB-backed per-client windows

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limits",
        sa.Column("bucket", sa.Text, primary_key=True),
        sa.Column("client", sa.Text, primary_key=True),
        sa.Column("window_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("count", sa.BigInteger, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("rate_limits")
