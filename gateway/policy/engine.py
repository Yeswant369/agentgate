"""Gathers the PolicyInput from the database — the impure half of the engine.

Race-proofing lives here: the mandate row is locked with SELECT ... FOR UPDATE
before spend is read, so two concurrent intents against a nearly-exhausted cap
serialize — exactly one sees the cap as available. The lock is transaction-
scoped (composes with Neon's pooler) and is released at commit.

All time arithmetic uses the DATABASE clock (now() in SQL): serverless app
instances have skewed clocks; the ledger has one.
"""

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from gateway.models import Mandate, Merchant, Product, Transaction
from gateway.policy.rules import (
    DUPLICATE_WINDOW_MINUTES,
    STRUCTURING_WINDOW_MINUTES,
    VELOCITY_WINDOW_MINUTES,
    PolicyInput,
)

# States that count as committed-or-reserved spend for cap accounting.
# Denied/expired/failed/refunded attempts must not consume the cap.
SPEND_STATES = ("initiated", "pending_approval", "authorized", "captured")


def lock_mandate(session: Session, mandate_id: str) -> Mandate | None:
    return session.execute(
        select(Mandate).where(Mandate.id == mandate_id).with_for_update()
    ).scalar_one_or_none()


def gather_input(
    session: Session,
    mandate: Mandate,
    agent_id: str,
    product: Product,
    merchant: Merchant,
    claimed_price_paise: int,
) -> PolicyInput:
    """Caller must already hold the mandate row lock (lock_mandate)."""
    spent_today = session.scalar(
        select(func.coalesce(func.sum(Transaction.amount_paise), 0)).where(
            Transaction.mandate_id == mandate.id,
            Transaction.current_state.in_(SPEND_STATES),
            Transaction.created_at >= func.date_trunc("day", func.now()),
        )
    )
    intents_in_window = session.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.mandate_id == mandate.id,
            Transaction.created_at
            >= func.now() - text(f"interval '{VELOCITY_WINDOW_MINUTES} minutes'"),
        )
    )
    duplicates = session.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.mandate_id == mandate.id,
            Transaction.product_id == product.id,
            Transaction.current_state.in_(SPEND_STATES),
            Transaction.created_at
            >= func.now() - text(f"interval '{DUPLICATE_WINDOW_MINUTES} minutes'"),
        )
    )
    merchant_window = session.execute(
        select(
            func.coalesce(func.sum(Transaction.amount_paise), 0),
            func.count(Transaction.id),
        ).where(
            Transaction.mandate_id == mandate.id,
            Transaction.merchant_id == merchant.id,
            Transaction.current_state.in_(SPEND_STATES),
            Transaction.created_at
            >= func.now() - text(f"interval '{STRUCTURING_WINDOW_MINUTES} minutes'"),
        )
    ).one()
    mandate_expired = bool(session.scalar(select(func.now() > mandate.expires_at)))

    return PolicyInput(
        agent_id=agent_id,
        mandate_id=mandate.id,
        mandate_revoked=mandate.revoked,
        mandate_expired=mandate_expired,
        merchant_allowlist=tuple(mandate.merchant_allowlist),
        allowed_categories=tuple(mandate.allowed_categories),
        max_txn_paise=mandate.max_txn_paise,
        daily_cap_paise=mandate.daily_cap_paise,
        merchant_id=merchant.id,
        merchant_category=merchant.category,
        product_id=product.id,
        catalog_price_paise=product.price_paise,
        claimed_price_paise=claimed_price_paise,
        amount_paise=product.price_paise,
        spent_today_paise=int(spent_today or 0),
        intents_in_velocity_window=int(intents_in_window or 0),
        duplicate_intents_in_window=int(duplicates or 0),
        merchant_spend_in_structuring_window_paise=int(merchant_window[0] or 0),
        merchant_txn_count_in_structuring_window=int(merchant_window[1] or 0),
    )
