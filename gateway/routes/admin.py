from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gateway.db import get_db
from gateway.ledger import append_event
from gateway.models import Agent, Mandate, Transaction, new_id
from gateway.security import generate_agent_key, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

APPROVAL_TTL_MINUTES = 60


class CreateAgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    max_txn_paise: int = Field(gt=0)
    daily_cap_paise: int = Field(gt=0)
    merchant_allowlist: list[str] = Field(min_length=1)
    allowed_categories: list[str] = Field(default_factory=list)
    mandate_days: int = Field(default=30, gt=0, le=365)


class CreateAgentOut(BaseModel):
    agent_id: str
    mandate_id: str
    api_key: str  # shown exactly once; only its hash is stored


@router.post("/agents", status_code=201)
def create_agent(body: CreateAgentIn, db: Session = Depends(get_db)) -> CreateAgentOut:
    plaintext, key_hash = generate_agent_key()
    agent = Agent(id=new_id("agt"), name=body.name, api_key_hash=key_hash)
    db.add(agent)
    db_now = db.execute(select(func.now())).scalar_one()
    expires = db_now + timedelta(days=body.mandate_days)
    mandate = Mandate(
        id=new_id("mdt"),
        agent_id=agent.id,
        max_txn_paise=body.max_txn_paise,
        daily_cap_paise=body.daily_cap_paise,
        merchant_allowlist=body.merchant_allowlist,
        allowed_categories=body.allowed_categories,
        expires_at=expires,
    )
    db.add(mandate)
    return CreateAgentOut(agent_id=agent.id, mandate_id=mandate.id, api_key=plaintext)


@router.post("/mandates/{mandate_id}/revoke")
def revoke_mandate(mandate_id: str, db: Session = Depends(get_db)) -> dict:
    mandate = db.get(Mandate, mandate_id)
    if mandate is None:
        raise HTTPException(status_code=404, detail="mandate not found")
    mandate.revoked = True
    return {"mandate_id": mandate_id, "revoked": True}


def _expire_if_stale(db: Session, txn: Transaction) -> bool:
    """TTL enforcement without a scheduler: staleness is checked (against DB
    time) whenever the approval is touched — stateless by design."""
    stale = db.scalar(
        select(func.now() > txn.created_at + timedelta(minutes=APPROVAL_TTL_MINUTES))
    )
    if stale:
        append_event(db, txn, "approval_expired", {"ttl_minutes": APPROVAL_TTL_MINUTES})
        return True
    return False


@router.post("/approvals/{transaction_id}/{action}")
def decide_approval(transaction_id: str, action: str, db: Session = Depends(get_db)) -> dict:
    if action not in {"approve", "deny"}:
        raise HTTPException(status_code=404, detail="action must be approve or deny")
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    if txn.current_state != "pending_approval":
        raise HTTPException(
            status_code=409, detail=f"transaction is {txn.current_state}, not pending_approval"
        )
    if _expire_if_stale(db, txn):
        raise HTTPException(status_code=410, detail="approval window expired")
    event = "approval_granted" if action == "approve" else "approval_denied"
    append_event(db, txn, event, {"by": "admin"})
    return {"transaction_id": txn.id, "state": txn.current_state}


@router.get("/approvals")
def list_pending(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Transaction)
        .where(Transaction.current_state == "pending_approval")
        .order_by(Transaction.created_at.desc())
        .limit(50)
    ).all()
    return [
        {
            "transaction_id": t.id,
            "amount_paise": t.amount_paise,
            "merchant_id": t.merchant_id,
            "agent_id": t.agent_id,
        }
        for t in rows
    ]
