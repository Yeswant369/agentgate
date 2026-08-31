from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gateway.audit import verify_chain
from gateway.db import get_db
from gateway.models import AuditRecord

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("")
def overview(db: Session = Depends(get_db)) -> dict:
    """Headline counters for the Overview page: totals, denials by the rule
    that fired, and the live chain-integrity badge."""
    total = db.scalar(select(func.count(AuditRecord.id))) or 0
    by_decision: dict[str, int] = {
        row[0]: int(row[1])
        for row in db.execute(
            select(AuditRecord.decision, func.count(AuditRecord.id)).group_by(
                AuditRecord.decision
            )
        ).all()
    }

    # Denials by the first non-passing rule — a quick "what gets blocked" view.
    deny_rows = db.scalars(
        select(AuditRecord.rule_results)
        .where(AuditRecord.decision == "deny")
        .order_by(AuditRecord.id.desc())
        .limit(500)
    ).all()
    reasons: Counter = Counter()
    for rules in deny_rows:
        for r in rules:
            if r.get("outcome") == "deny":
                reasons[r["rule_id"]] += 1
                break

    chain = verify_chain(db)
    return {
        "total_decisions": int(total),
        "by_decision": by_decision,
        "denials_by_rule": dict(reasons.most_common(10)),
        "chain": {"intact": chain["intact"], "length": chain.get("length", 0)},
    }
