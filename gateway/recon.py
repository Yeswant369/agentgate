"""Reconciliation: our ledger vs Razorpay's records.

The books must match the provider's books, provably. Every run produces a
persisted report: matched, amount-mismatched, missing on either side.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.models import ReconRun, Transaction
from gateway.payments.razorpay_client import RazorpayClient

logger = logging.getLogger("gateway.recon")


@dataclass
class ReconReport:
    matched: int = 0
    mismatched: int = 0
    missing_local: int = 0
    missing_remote: int = 0
    details: list[dict] = field(default_factory=list)


def run_reconciliation(session: Session, client: RazorpayClient | None = None) -> ReconReport:
    client = client or RazorpayClient()
    report = ReconReport()

    remote_orders: dict[str, dict] = {}
    skip = 0
    while True:
        batch = client.list_orders(count=100, skip=skip)
        for order in batch:
            remote_orders[order["id"]] = order
        if len(batch) < 100:
            break
        skip += 100

    local_txns = session.scalars(
        select(Transaction).where(Transaction.razorpay_order_id.is_not(None))
    ).all()
    local_by_order = {t.razorpay_order_id: t for t in local_txns}

    for order_id, txn in local_by_order.items():
        remote = remote_orders.get(order_id or "")
        if remote is None:
            report.missing_remote += 1
            report.details.append(
                {"kind": "missing_remote", "txn_id": txn.id, "order_id": order_id}
            )
            continue
        if remote.get("amount") != txn.amount_paise:
            report.mismatched += 1
            report.details.append(
                {
                    "kind": "amount_mismatch",
                    "txn_id": txn.id,
                    "order_id": order_id,
                    "local_paise": txn.amount_paise,
                    "remote_paise": remote.get("amount"),
                }
            )
            continue
        report.matched += 1

    # Remote orders whose receipt claims to be one of our transactions but
    # which our ledger has no record of — the scarier direction.
    local_ids = {t.id for t in local_txns}
    for order_id, remote in remote_orders.items():
        receipt = str(remote.get("receipt", ""))
        if receipt.startswith("txn_") and receipt not in local_ids:
            report.missing_local += 1
            report.details.append(
                {"kind": "missing_local", "order_id": order_id, "receipt": receipt}
            )

    session.add(
        ReconRun(
            matched=report.matched,
            mismatched=report.mismatched,
            missing_local=report.missing_local,
            missing_remote=report.missing_remote,
            details={"items": report.details[:200]},
        )
    )
    session.commit()
    return report
