"""trust gateway: agents, mandates, audit chain

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("api_key_hash", sa.Text, nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "mandates",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("agent_id", sa.Text, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("max_txn_paise", sa.BigInteger, nullable=False),
        sa.Column("daily_cap_paise", sa.BigInteger, nullable=False),
        sa.Column("merchant_allowlist", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("allowed_categories", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("max_txn_paise > 0", name="ck_mandate_txn_cap_positive"),
        sa.CheckConstraint("daily_cap_paise > 0", name="ck_mandate_daily_cap_positive"),
    )
    op.create_index("ix_mandates_agent_id", "mandates", ["agent_id"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.Text, nullable=False),
        sa.Column("agent_id", sa.Text, nullable=True),
        sa.Column("mandate_id", sa.Text, nullable=True),
        sa.Column("transaction_id", sa.Text, nullable=True),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("policy_version", sa.BigInteger, nullable=False),
        sa.Column("input_snapshot", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("rule_results", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("prev_hash", sa.Text, nullable=False),
        sa.Column("hash", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column("transactions", sa.Column("agent_id", sa.Text, nullable=True))
    op.add_column("transactions", sa.Column("mandate_id", sa.Text, nullable=True))
    op.create_index("ix_transactions_agent_id", "transactions", ["agent_id"])
    op.create_index("ix_transactions_mandate_id", "transactions", ["mandate_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_mandate_id", "transactions")
    op.drop_index("ix_transactions_agent_id", "transactions")
    op.drop_column("transactions", "mandate_id")
    op.drop_column("transactions", "agent_id")
    op.drop_table("audit_log")
    op.drop_table("mandates")
    op.drop_table("agents")
