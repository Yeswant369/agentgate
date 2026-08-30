"""Event-sourced transaction ledger.

Transactions never mutate a status string in place. Every change is an
appended event; the current state is a function of the event history and the
cached `current_state` column must always equal the replayed derivation.
An illegal transition raises loudly — it means a code bug or a forged input,
and both must be impossible to paper over.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from gateway.models import Transaction, TransactionEvent

logger = logging.getLogger("gateway.ledger")

NEW_STATE = "__new__"  # pre-birth sentinel; only intent_created leaves it, and
# it never survives to a committed row because append_event runs first.
INITIAL_STATE = "initiated"

# event_type -> (required_current_state(s), resulting_state)
TRANSITIONS: dict[str, tuple[frozenset[str], str]] = {
    "intent_created": (frozenset({"__new__"}), "initiated"),
    "provider_order_created": (frozenset({"initiated"}), "initiated"),
    "payment_authorized": (frozenset({"initiated"}), "authorized"),
    "payment_captured": (frozenset({"authorized", "initiated"}), "captured"),
    # Razorpay may deliver captured without a separate authorized event.
    "payment_failed": (frozenset({"initiated", "authorized"}), "failed"),
    "refund_initiated": (frozenset({"captured"}), "refund_pending"),
    "refund_processed": (frozenset({"refund_pending"}), "refunded"),
    "refund_failed": (frozenset({"refund_pending"}), "captured"),
    # Recorded observations that do not change state:
    "amount_mismatch_flagged": (frozenset(), ""),
    "provider_error": (frozenset(), ""),
}


class IllegalTransition(RuntimeError):
    def __init__(self, txn_id: str, current: str, event_type: str):
        self.txn_id, self.current, self.event_type = txn_id, current, event_type
        super().__init__(
            f"illegal transition: transaction {txn_id} in state {current!r} "
            f"cannot accept event {event_type!r}"
        )


def next_state(current: str, event_type: str) -> str:
    """Pure transition function. Returns the resulting state, or the current
    state unchanged for observation-only events. Raises IllegalTransition."""
    if event_type not in TRANSITIONS:
        raise IllegalTransition("?", current, event_type)
    allowed_from, result = TRANSITIONS[event_type]
    if not allowed_from:  # observation-only event
        return current
    if current not in allowed_from:
        raise IllegalTransition("?", current, event_type)
    return result


def derive_state(event_types: list[str]) -> str:
    """Replay a full event history from scratch. The cached column on the
    transaction row must always equal this — tested, not assumed."""
    state = "__new__"
    for event_type in event_types:
        state = next_state(state, event_type)
    return state


def append_event(
    session: Session,
    txn: Transaction,
    event_type: str,
    data: dict[str, Any] | None = None,
) -> str:
    """Validate the transition, append the immutable event, update the cached
    state. Caller owns the enclosing DB transaction (atomicity lives there)."""
    try:
        new_state = next_state(txn.current_state, event_type)
    except IllegalTransition:
        raise IllegalTransition(txn.id, txn.current_state, event_type) from None
    session.add(TransactionEvent(transaction_id=txn.id, event_type=event_type, data=data or {}))
    txn.current_state = new_state
    return new_state
