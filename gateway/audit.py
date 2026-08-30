"""Hash-chained audit log.

Every policy decision — allows, denies, step-ups and system errors alike —
appends a record whose hash covers the previous record's hash plus its own
canonical content. Tampering with any historical row breaks every hash after
it. Appends take a Postgres advisory lock (transaction-scoped) so concurrent
writers cannot fork the chain.

No blockchain. A hash chain in Postgres gives tamper-EVIDENCE, which is what
an audit trail needs; consensus infrastructure would add nothing here.
"""

import hashlib
import json
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from gateway.models import AuditRecord

GENESIS_HASH = "0" * 64
# Arbitrary constant key for pg_advisory_xact_lock; one chain, one lock.
AUDIT_CHAIN_LOCK_KEY = 847_291_337


def canonical(record_content: dict[str, Any]) -> str:
    return json.dumps(record_content, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, record_content: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical(record_content)).encode()).hexdigest()


def _content(record: AuditRecord) -> dict[str, Any]:
    return {
        "request_id": record.request_id,
        "agent_id": record.agent_id,
        "mandate_id": record.mandate_id,
        "transaction_id": record.transaction_id,
        "decision": record.decision,
        "policy_version": record.policy_version,
        "input_snapshot": record.input_snapshot,
        "rule_results": record.rule_results,
    }


def append_audit(
    session: Session,
    *,
    request_id: str,
    agent_id: str | None,
    mandate_id: str | None,
    transaction_id: str | None,
    decision: str,
    policy_version: int,
    input_snapshot: dict[str, Any],
    rule_results: list[dict[str, Any]],
) -> AuditRecord:
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": AUDIT_CHAIN_LOCK_KEY})
    prev = session.execute(
        select(AuditRecord).order_by(AuditRecord.id.desc()).limit(1)
    ).scalar_one_or_none()
    prev_hash = prev.hash if prev is not None else GENESIS_HASH

    record = AuditRecord(
        request_id=request_id,
        agent_id=agent_id,
        mandate_id=mandate_id,
        transaction_id=transaction_id,
        decision=decision,
        policy_version=policy_version,
        input_snapshot=input_snapshot,
        rule_results=rule_results,
        prev_hash=prev_hash,
    )
    record.hash = compute_hash(prev_hash, _content(record))
    session.add(record)
    session.flush()
    return record


def verify_chain(session: Session) -> dict[str, Any]:
    """Re-walk the whole chain and recompute every hash. Returns the first
    break if any — an intact result is a computation, not a claim."""
    records = session.scalars(select(AuditRecord).order_by(AuditRecord.id)).all()
    prev_hash = GENESIS_HASH
    for record in records:
        if record.prev_hash != prev_hash:
            return {"intact": False, "broken_at": record.id, "reason": "prev_hash mismatch"}
        expected = compute_hash(prev_hash, _content(record))
        if record.hash != expected:
            return {"intact": False, "broken_at": record.id, "reason": "content hash mismatch"}
        prev_hash = record.hash
    return {"intact": True, "length": len(records), "head": prev_hash}
