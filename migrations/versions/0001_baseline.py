"""baseline: system_meta

Revision ID: 0001
Revises:
Create Date: 2026-08-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_meta",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "INSERT INTO system_meta (key, value) VALUES ('boot_check', 'ok'), ('schema_phase', '1')"
    )


def downgrade() -> None:
    op.drop_table("system_meta")
