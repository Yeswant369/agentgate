import hashlib
import hmac
import json
import uuid

from gateway.config import get_settings
from tests.conftest import requires_db

pytestmark = requires_db


def _signed_webhook(client, payload: dict, event_id: str):
    body = json.dumps(payload).encode()
    signature = hmac.new(
        get_settings().razorpay_webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": event_id,
            "Content-Type": "application/json",
        },
    )


def _captured_payload(order_id: str, amount: int) -> dict:
    return {
        "event": "payment.captured",
        "payload": {
            "payment": {"entity": {"id": "pay_test123", "order_id": order_id, "amount": amount}}
        },
    }


def _create_order(client, seeded_product) -> dict:
    return client.post(
        "/api/orders",
        json={"product_id": seeded_product["product_id"]},
        headers={"Idempotency-Key": f"key-{uuid.uuid4().hex}"},
    ).json()


def test_unsigned_webhook_rejected(client):
    resp = client.post(
        "/api/webhooks/razorpay",
        content=b'{"event":"payment.captured"}',
        headers={"X-Razorpay-Event-Id": "evt_forged"},
    )
    assert resp.status_code == 401


def test_webhook_delivered_three_times_captures_exactly_once(
    client, seeded_product, stub_provider
):
    order = _create_order(client, seeded_product)
    suffix = seeded_product["product_id"].removeprefix("p_test_")
    event_id = f"evt_test_{suffix}_{uuid.uuid4().hex[:6]}"
    payload = _captured_payload(order["razorpay_order_id"], order["amount_paise"])

    results = [_signed_webhook(client, payload, event_id).json() for _ in range(3)]
    assert results[0]["status"] == "processed"
    assert results[1]["status"] == "duplicate"
    assert results[2]["status"] == "duplicate"

    txn = client.get(f"/api/orders/{order['transaction_id']}").json()
    assert txn["state"] == "captured"


def test_webhook_amount_mismatch_is_flagged_not_applied(client, seeded_product, stub_provider):
    order = _create_order(client, seeded_product)
    suffix = seeded_product["product_id"].removeprefix("p_test_")
    payload = _captured_payload(order["razorpay_order_id"], order["amount_paise"] + 1)

    resp = _signed_webhook(client, payload, f"evt_test_{suffix}_mismatch")
    assert resp.json()["status"] == "ignored"
    txn = client.get(f"/api/orders/{order['transaction_id']}").json()
    assert txn["state"] == "initiated"  # no transition on untrusted amounts
