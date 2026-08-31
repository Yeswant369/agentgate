"""agent sessions: transcripts + honesty verdicts

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("agent_id", sa.Text, nullable=False),
        sa.Column("intent", sa.Text, nullable=False),
        sa.Column("scenario", sa.Text, nullable=True),
        sa.Column("transcript", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("claimed", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("actual", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("honest", sa.Boolean, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_sessions_agent_id", "agent_sessions", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_sessions_agent_id", "agent_sessions")
    op.drop_table("agent_sessions")
