import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gateway.db import get_db
from gateway.ledger import NEW_STATE, append_event
from gateway.logging import log_with
from gateway.models import Product, Transaction, new_id
from gateway.money import Money
from gateway.payments.razorpay_client import (
    RazorpayClient,
    RazorpayError,
)

logger = logging.getLogger("gateway.orders")

router = APIRouter(prefix="/api/orders", tags=["orders"])


class CreateOrderIn(BaseModel):
    product_id: str = Field(min_length=1, max_length=128)


class OrderOut(BaseModel):
    transaction_id: str
    razorpay_order_id: str | None
    amount_paise: int
    currency: str
    state: str
    idempotent_replay: bool = False


def _to_out(txn: Transaction, replay: bool = False) -> OrderOut:
    return OrderOut(
        transaction_id=txn.id,
        razorpay_order_id=txn.razorpay_order_id,
        amount_paise=txn.amount_paise,
        currency=txn.currency,
        state=txn.current_state,
        idempotent_replay=replay,
    )


@router.post("", status_code=201)
def create_order(
    body: CreateOrderIn,
    idempotency_key: str = Header(min_length=8, max_length=128),
    db: Session = Depends(get_db),
) -> OrderOut:
    """Create a purchase order.

    Two properties matter here:
    - The price comes from OUR catalog, never from the request body. A client
      (or a manipulated agent) cannot name its own price.
    - The Idempotency-Key header is required and unique: a retried request
      returns the original transaction, never a second charge.
    """
    existing = db.scalar(
        select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return _to_out(existing, replay=True)

    product = db.get(Product, body.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")

    amount = Money(product.price_paise, product.currency)
    txn = Transaction(
        id=new_id("txn"),
        merchant_id=product.merchant_id,
        product_id=product.id,
        amount_paise=amount.paise,
        currency=amount.currency,
        current_state=NEW_STATE,
        idempotency_key=idempotency_key,
    )
    db.add(txn)
    append_event(db, txn, "intent_created", {"product_id": product.id})
    try:
        db.flush()
    except IntegrityError:
        # Two concurrent requests raced the same idempotency key; the UNIQUE
        # constraint is the arbiter. Return the winner's transaction.
        db.rollback()
        winner = db.scalar(
            select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        )
        if winner is None:
            raise HTTPException(status_code=409, detail="idempotency conflict") from None
        return _to_out(winner, replay=True)

    try:
        order = RazorpayClient().create_order(amount, receipt=txn.id)
    except RazorpayError as exc:
        # Fail into a safe state: the intent exists, no provider order does.
        append_event(db, txn, "provider_error", {"error": str(exc)})
        log_with(logger, logging.ERROR, "provider order failed", txn_id=txn.id)
        raise HTTPException(
            status_code=502,
            detail="payment provider unavailable; retry with the same Idempotency-Key",
        ) from exc

    txn.razorpay_order_id = order["id"]
    append_event(db, txn, "provider_order_created", {"razorpay_order_id": order["id"]})
    return _to_out(txn)


@router.get("/{transaction_id}")
def get_order(transaction_id: str, db: Session = Depends(get_db)) -> OrderOut:
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return _to_out(txn)
