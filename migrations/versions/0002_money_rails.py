"""money rails: catalog, ledger, webhooks, recon

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "merchant_id", sa.Text, sa.ForeignKey("merchants.id"), nullable=False
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("price_paise", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.Text, nullable=False, server_default="INR"),
        sa.Column("attack_class", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("price_paise > 0", name="ck_products_price_positive"),
    )
    op.create_index("ix_products_merchant_id", "products", ["merchant_id"])
    op.create_table(
        "transactions",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "merchant_id", sa.Text, sa.ForeignKey("merchants.id"), nullable=False
        ),
        sa.Column("product_id", sa.Text, sa.ForeignKey("products.id"), nullable=True),
        sa.Column("amount_paise", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.Text, nullable=False, server_default="INR"),
        sa.Column("current_state", sa.Text, nullable=False),
        sa.Column("idempotency_key", sa.Text, nullable=False, unique=True),
        sa.Column("razorpay_order_id", sa.Text, nullable=True, unique=True),
        sa.Column("razorpay_payment_id", sa.Text, nullable=True),
        sa.Column("captured_paise", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("refunded_paise", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_paise > 0", name="ck_txn_amount_positive"),
        sa.CheckConstraint(
            "refunded_paise >= 0 AND refunded_paise <= captured_paise",
            name="ck_txn_refund_le_captured",
        ),
    )
    op.create_table(
        "transaction_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "transaction_id", sa.Text, sa.ForeignKey("transactions.id"), nullable=False
        ),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("data", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_txn_events_txn_id_id", "transaction_events", ["transaction_id", "id"]
    )
    op.create_table(
        "webhook_events",
        sa.Column("event_id", sa.Text, primary_key=True),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("processed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "recon_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "ran_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("matched", sa.BigInteger, nullable=False),
        sa.Column("mismatched", sa.BigInteger, nullable=False),
        sa.Column("missing_local", sa.BigInteger, nullable=False),
        sa.Column("missing_remote", sa.BigInteger, nullable=False),
        sa.Column("details", sa.JSON, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    for table in (
        "recon_runs",
        "webhook_events",
        "transaction_events",
        "transactions",
        "products",
        "merchants",
    ):
        op.drop_table(table)
