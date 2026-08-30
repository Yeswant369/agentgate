import pytest

from gateway.ledger import IllegalTransition, derive_state, next_state


def test_happy_path_authorize_then_capture():
    state = next_state("__new__", "intent_created")
    state = next_state(state, "provider_order_created")
    state = next_state(state, "payment_authorized")
    state = next_state(state, "payment_captured")
    assert state == "captured"


def test_direct_capture_without_authorized_event():
    # Razorpay may deliver payment.captured without a separate authorized event.
    assert next_state("initiated", "payment_captured") == "captured"


def test_illegal_transition_raises_loudly():
    with pytest.raises(IllegalTransition):
        next_state("captured", "payment_authorized")
    with pytest.raises(IllegalTransition):
        next_state("refunded", "payment_captured")


def test_unknown_event_type_raises():
    with pytest.raises(IllegalTransition):
        next_state("initiated", "totally_made_up")


def test_observation_events_do_not_change_state():
    assert next_state("initiated", "amount_mismatch_flagged") == "initiated"
    assert next_state("captured", "provider_error") == "captured"


def test_refund_lifecycle():
    state = next_state("captured", "refund_initiated")
    assert state == "refund_pending"
    assert next_state(state, "refund_processed") == "refunded"
    assert next_state("refund_pending", "refund_failed") == "captured"


def test_derived_state_replays_full_history():
    events = [
        "intent_created",
        "provider_order_created",
        "amount_mismatch_flagged",
        "payment_authorized",
        "payment_captured",
        "refund_initiated",
        "refund_processed",
    ]
    assert derive_state(events) == "refunded"
