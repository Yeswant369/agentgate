import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    # DB time, never app-server time: serverless instances have skewed clocks.
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class Merchant(TimestampMixin, Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        ForeignKey("merchants.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="INR")
    # Phase 4: tags poisoned listings for the eval harness. NEVER exposed via
    # the agent-facing API.
    attack_class: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (CheckConstraint("price_paise > 0", name="ck_products_price_positive"),)


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="INR")
    current_state: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    mandate_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    refunded_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_txn_amount_positive"),
        # A refund can never exceed what was captured — enforced by the
        # database itself, not just application code.
        CheckConstraint(
            "refunded_paise >= 0 AND refunded_paise <= captured_paise",
            name="ck_txn_refund_le_captured",
        ),
    )


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Only the SHA-256 of the API key is stored; the key itself is shown once
    # at creation and never again.
    api_key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class Mandate(TimestampMixin, Base):
    __tablename__ = "mandates"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    max_txn_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    daily_cap_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Allowlisting is by merchant ID, never by name: unicode lookalike names
    # must not be able to impersonate an allowed merchant.
    merchant_allowlist: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint("max_txn_paise > 0", name="ck_mandate_txn_cap_positive"),
        CheckConstraint("daily_cap_paise > 0", name="ck_mandate_daily_cap_positive"),
    )


class AuditRecord(Base):
    __tablename__ = "audit_log"

    # Monotonic sequence: appends are serialized under an advisory lock so the
    # chain can never fork under concurrency.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    mandate_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(Text, nullable=False)  # allow|deny|step_up
    policy_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # The full policy INPUT snapshot + per-rule results: what was decided,
    # from what evidence, by which ruleset — enough to replay deterministically.
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    rule_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    prev_hash: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class TransactionEvent(Base):
    __tablename__ = "transaction_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_txn_events_txn_id_id", "transaction_id", "id"),)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    # Razorpay's event id is the primary key: a redelivered webhook violates
    # the constraint and is acknowledged without being processed twice.
    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    # The hallucination detector's inputs and verdict: what the agent CLAIMED
    # happened vs what the ledger says ACTUALLY happened.
    claimed: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    actual: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    honest: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ran_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)  # replay | live
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Full metrics blob: confusion matrix, per-class detection w/ CIs, mutation
    # results, FP cost. Kept forever — unflattering runs stay in the history.
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ReconRun(Base):
    __tablename__ = "recon_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ran_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    matched: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mismatched: Mapped[int] = mapped_column(BigInteger, nullable=False)
    missing_local: Mapped[int] = mapped_column(BigInteger, nullable=False)
    missing_remote: Mapped[int] = mapped_column(BigInteger, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
