import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gateway.audit import append_audit
from gateway.db import get_db
from gateway.ledger import NEW_STATE, append_event
from gateway.logging import log_with, request_id_var
from gateway.models import Agent, Mandate, Merchant, Product, Transaction, new_id
from gateway.policy.engine import gather_input, lock_mandate
from gateway.policy.rules import POLICY_VERSION, evaluate
from gateway.security import hash_agent_key

logger = logging.getLogger("gateway.intents")

router = APIRouter(prefix="/api/purchase-intents", tags=["purchase-intents"])


class IntentIn(BaseModel):
    product_id: str = Field(min_length=1, max_length=128)
    # What the agent BELIEVES the price is. A manipulated agent that absorbed
    # an injected price fails price_integrity even though we charge catalog.
    claimed_price_paise: int = Field(gt=0)


class IntentOut(BaseModel):
    transaction_id: str
    decision: str
    state: str
    reasons: list[dict]
    amount_paise: int
    audit_id: int
    idempotent_replay: bool = False


def _authenticate(db: Session, agent_key: str) -> tuple[Agent, Mandate]:
    agent = db.scalar(select(Agent).where(Agent.api_key_hash == hash_agent_key(agent_key)))
    if agent is None:
        raise HTTPException(status_code=401, detail="invalid agent key")
    mandate = db.scalar(
        select(Mandate)
        .where(Mandate.agent_id == agent.id)
        .order_by(Mandate.created_at.desc())
        .limit(1)
    )
    if mandate is None:
        raise HTTPException(status_code=403, detail="agent has no mandate")
    return agent, mandate


def _deny_reasons(rule_results: list[dict]) -> list[dict]:
    """What the AGENT gets back: rule ids + reasons for non-passing rules only.
    Full evidence stays in the audit log — we do not hand the policed party a
    map of the policy internals."""
    return [
        {"rule_id": r["rule_id"], "outcome": r["outcome"], "reason": r["reason"]}
        for r in rule_results
        if r["outcome"] != "pass"
    ]


@router.post("", status_code=201)
def create_intent(
    body: IntentIn,
    x_agent_key: str = Header(min_length=8),
    idempotency_key: str = Header(min_length=8, max_length=128),
    db: Session = Depends(get_db),
) -> IntentOut:
    agent, mandate = _authenticate(db, x_agent_key)

    existing = db.scalar(
        select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.agent_id != agent.id:
            raise HTTPException(
                status_code=409, detail="idempotency key owned by another agent"
            )
        return _replay_out(db, existing)

    product = db.get(Product, body.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    merchant = db.get(Merchant, product.merchant_id)
    if merchant is None:
        raise HTTPException(status_code=404, detail="merchant not found")

    # ---- fail-closed boundary: everything below must succeed or the answer is deny
    try:
        locked = lock_mandate(db, mandate.id)
        if locked is None:
            raise RuntimeError("mandate row vanished under lock")
        policy_input = gather_input(
            db, locked, agent.id, product, merchant, body.claimed_price_paise
        )
        decision = evaluate(policy_input)
    except Exception:
        logger.exception("policy evaluation failed — failing closed")
        db.rollback()
        record = append_audit(
            db,
            request_id=request_id_var.get(),
            agent_id=agent.id,
            mandate_id=mandate.id,
            transaction_id=None,
            decision="deny",
            policy_version=POLICY_VERSION,
            input_snapshot={"error": "policy evaluation failed"},
            rule_results=[
                {
                    "rule_id": "system_error",
                    "outcome": "deny",
                    "reason": "gateway could not evaluate policy; an unavailable "
                    "gateway never approves",
                    "evidence": {},
                }
            ],
        )
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=f"policy engine unavailable; denied fail-closed (audit_id={record.id})",
        ) from None

    txn = Transaction(
        id=new_id("txn"),
        merchant_id=merchant.id,
        product_id=product.id,
        amount_paise=policy_input.amount_paise,
        currency=product.currency,
        current_state=NEW_STATE,
        idempotency_key=idempotency_key,
        agent_id=agent.id,
        mandate_id=mandate.id,
    )
    db.add(txn)
    append_event(db, txn, "intent_created", {"product_id": product.id, "agent_id": agent.id})

    if decision.decision == "deny":
        append_event(
            db, txn, "policy_denied", {"rules": _deny_reasons(decision.to_rule_dicts())}
        )
    elif decision.decision == "step_up":
        append_event(db, txn, "policy_step_up", {})

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        winner = db.scalar(
            select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        )
        if winner is None:
            raise HTTPException(status_code=409, detail="idempotency conflict") from None
        return _replay_out(db, winner)

    record = append_audit(
        db,
        request_id=request_id_var.get(),
        agent_id=agent.id,
        mandate_id=mandate.id,
        transaction_id=txn.id,
        decision=decision.decision,
        policy_version=decision.policy_version,
        input_snapshot=policy_input.to_snapshot(),
        rule_results=decision.to_rule_dicts(),
    )
    log_with(
        logger,
        logging.INFO,
        "policy decision",
        txn_id=txn.id,
        decision=decision.decision,
        audit_id=record.id,
        agent_id=agent.id,
    )
    return IntentOut(
        transaction_id=txn.id,
        decision=decision.decision,
        state=txn.current_state,
        reasons=_deny_reasons(decision.to_rule_dicts()),
        amount_paise=txn.amount_paise,
        audit_id=record.id,
    )


def _replay_out(db: Session, txn: Transaction) -> IntentOut:
    from gateway.models import AuditRecord

    record = db.scalar(
        select(AuditRecord)
        .where(AuditRecord.transaction_id == txn.id)
        .order_by(AuditRecord.id.desc())
        .limit(1)
    )
    decision = record.decision if record is not None else "unknown"
    return IntentOut(
        transaction_id=txn.id,
        decision=decision,
        state=txn.current_state,
        reasons=[],
        amount_paise=txn.amount_paise,
        audit_id=record.id if record is not None else 0,
        idempotent_replay=True,
    )
