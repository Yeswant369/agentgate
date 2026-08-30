import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gateway.config import get_settings
from gateway.db import get_db
from gateway.ledger import append_event
from gateway.logging import log_with
from gateway.models import Transaction, WebhookEvent
from gateway.payments.webhook_signature import verify_webhook_signature

logger = logging.getLogger("gateway.webhooks")

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str = Header(default=""),
    x_razorpay_event_id: str = Header(default=""),
) -> dict:
    """Razorpay webhook receiver.

    Order of operations is deliberate:
    1. Verify the HMAC signature over the RAW body (constant time) — unsigned
       junk never touches the database.
    2. Claim the event id under a UNIQUE constraint — Razorpay redelivers
       webhooks, and a duplicate must be acknowledged but never re-processed.
    3. Cross-check payload amounts against OUR ledger — the webhook is
       evidence, not truth.
    """
    body = await request.body()
    settings = get_settings()
    if not verify_webhook_signature(
        body, x_razorpay_signature, settings.razorpay_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    if not x_razorpay_event_id:
        raise HTTPException(status_code=400, detail="missing X-Razorpay-Event-Id")

    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid JSON body") from None
    event_type = str(payload.get("event", ""))

    db.add(WebhookEvent(event_id=x_razorpay_event_id, event_type=event_type, processed=False))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        log_with(logger, logging.INFO, "webhook replay ignored", event_id=x_razorpay_event_id)
        return {"status": "duplicate", "event_id": x_razorpay_event_id}

    handled = _handle_event(db, event_type, payload)
    claimed = db.get(WebhookEvent, x_razorpay_event_id)
    if claimed is not None:
        claimed.processed = handled
    return {"status": "processed" if handled else "ignored", "event": event_type}


def _payment_entity(payload: dict) -> dict:
    entity: dict = payload.get("payload", {}).get("payment", {}).get("entity", {})
    return entity


def _find_txn(db: Session, order_id: str) -> Transaction | None:
    if not order_id:
        return None
    return db.scalar(select(Transaction).where(Transaction.razorpay_order_id == order_id))


def _handle_event(db: Session, event_type: str, payload: dict) -> bool:
    if event_type not in {"payment.authorized", "payment.captured", "refund.processed"}:
        log_with(logger, logging.INFO, "webhook event ignored", event_type=event_type)
        return False

    if event_type == "refund.processed":
        # Refund initiation is a Phase 3 gateway flow; until then we record
        # the delivery (dedupe row already written) and take no ledger action.
        refund: dict = payload.get("payload", {}).get("refund", {}).get("entity", {})
        log_with(logger, logging.INFO, "refund webhook received", refund_id=refund.get("id"))
        return False

    entity = _payment_entity(payload)
    order_id = str(entity.get("order_id", ""))
    amount = entity.get("amount")
    txn = _find_txn(db, order_id)
    if txn is None:
        log_with(logger, logging.WARNING, "webhook for unknown order", order_id=order_id)
        return False

    # The webhook's amount must equal our ledger's amount. On mismatch we
    # record the observation and refuse the transition — recon will surface it.
    if not isinstance(amount, int) or amount != txn.amount_paise:
        append_event(
            db,
            txn,
            "amount_mismatch_flagged",
            {"webhook_amount": amount, "ledger_amount": txn.amount_paise, "event": event_type},
        )
        log_with(
            logger,
            logging.ERROR,
            "webhook amount mismatch",
            txn_id=txn.id,
            webhook_amount=amount,
            ledger_amount=txn.amount_paise,
        )
        return False

    if event_type == "payment.authorized":
        append_event(db, txn, "payment_authorized", {"payment_id": entity.get("id")})
    else:  # payment.captured
        append_event(db, txn, "payment_captured", {"payment_id": entity.get("id")})
        txn.captured_paise = txn.amount_paise
    txn.razorpay_payment_id = str(entity.get("id", "")) or txn.razorpay_payment_id
    return True
