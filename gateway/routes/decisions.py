from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.audit import verify_chain
from gateway.db import get_db
from gateway.models import AuditRecord
from gateway.policy.rules import RULESETS, PolicyInput, evaluate

router = APIRouter(prefix="/api", tags=["decisions"])


def _summary(r: AuditRecord) -> dict:
    return {
        "audit_id": r.id,
        "decision": r.decision,
        "agent_id": r.agent_id,
        "transaction_id": r.transaction_id,
        "policy_version": r.policy_version,
        "created_at": r.created_at.isoformat(),
        "failed_rules": [
            {"rule_id": x["rule_id"], "outcome": x["outcome"], "reason": x["reason"]}
            for x in r.rule_results
            if x["outcome"] != "pass"
        ],
    }


@router.get("/decisions")
def list_decisions(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    limit = max(1, min(limit, 200))
    rows = db.scalars(select(AuditRecord).order_by(AuditRecord.id.desc()).limit(limit)).all()
    return [_summary(r) for r in rows]


@router.get("/decisions/{audit_id}")
def get_decision(audit_id: int, db: Session = Depends(get_db)) -> dict:
    r = db.get(AuditRecord, audit_id)
    if r is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return {
        **_summary(r),
        "rule_results": r.rule_results,
        "input_snapshot": r.input_snapshot,
        "hash": r.hash,
        "prev_hash": r.prev_hash,
    }


@router.post("/decisions/{audit_id}/replay")
def replay_decision(audit_id: int, db: Session = Depends(get_db)) -> dict:
    """Deterministic replay: re-run the recorded inputs through the recorded
    policy version and compare. Determinism proven on demand, not claimed."""
    r = db.get(AuditRecord, audit_id)
    if r is None:
        raise HTTPException(status_code=404, detail="decision not found")
    if r.policy_version not in RULESETS:
        raise HTTPException(
            status_code=409, detail=f"policy version {r.policy_version} no longer available"
        )
    if "error" in r.input_snapshot:
        raise HTTPException(status_code=409, detail="system-error decisions cannot be replayed")

    replayed = evaluate(PolicyInput.from_snapshot(r.input_snapshot), version=r.policy_version)
    identical = replayed.decision == r.decision and replayed.to_rule_dicts() == r.rule_results
    return {
        "audit_id": r.id,
        "original_decision": r.decision,
        "replayed_decision": replayed.decision,
        "identical": identical,
        "policy_version": r.policy_version,
    }


@router.get("/audit/verify")
def audit_verify(db: Session = Depends(get_db)) -> dict:
    return verify_chain(db)


@router.get("/audit/records")
def audit_records(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    limit = max(1, min(limit, 200))
    rows = db.scalars(select(AuditRecord).order_by(AuditRecord.id.desc()).limit(limit)).all()
    return [
        {
            "id": r.id,
            "decision": r.decision,
            "transaction_id": r.transaction_id,
            "hash": r.hash[:16] + "…",
            "prev_hash": r.prev_hash[:16] + "…",
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
