"""End-to-end smoke test against a running gateway (default: local).

Creates a REAL Razorpay test-mode order, then simulates the payment.captured
webhook — correctly signed, delivered three times — and asserts the ledger
captured exactly once. This is the Phase 2 Definition-of-Done script.

Usage: python scripts/e2e_smoke.py [base_url]
"""

import hashlib
import hmac
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from gateway.config import get_settings  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def main() -> None:
    secret = get_settings().razorpay_webhook_secret
    assert secret, "RAZORPAY_WEBHOOK_SECRET must be set"
    client = httpx.Client(base_url=BASE, timeout=30)

    products = client.get("/api/catalog/products", params={"q": "chai"}).json()
    assert products, "catalog is empty — run scripts/seed_catalog.py first"
    product = products[0]
    print(f"1. product: {product['title']} @ {product['price_paise']} paise")

    key = f"e2e-{uuid.uuid4().hex}"
    order = client.post(
        "/api/orders",
        json={"product_id": product["id"]},
        headers={"Idempotency-Key": key},
    )
    assert order.status_code == 201, order.text
    txn = order.json()
    print(f"2. real Razorpay order: {txn['razorpay_order_id']} (state={txn['state']})")

    replay = client.post(
        "/api/orders", json={"product_id": product["id"]}, headers={"Idempotency-Key": key}
    ).json()
    assert replay["transaction_id"] == txn["transaction_id"]
    assert replay["idempotent_replay"] is True
    print("3. idempotent retry returned the SAME transaction — no double charge")

    payload = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_e2e{uuid.uuid4().hex[:10]}",
                        "order_id": txn["razorpay_order_id"],
                        "amount": txn["amount_paise"],
                    }
                }
            },
        }
    ).encode()
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    event_id = f"evt_e2e_{uuid.uuid4().hex[:12]}"
    headers = {
        "X-Razorpay-Signature": signature,
        "X-Razorpay-Event-Id": event_id,
        "Content-Type": "application/json",
    }
    statuses = [
        client.post("/api/webhooks/razorpay", content=payload, headers=headers).json()["status"]
        for _ in range(3)
    ]
    assert statuses == ["processed", "duplicate", "duplicate"], statuses
    print(f"4. webhook delivered 3x -> {statuses} (captured exactly once)")

    final = client.get(f"/api/orders/{txn['transaction_id']}").json()
    assert final["state"] == "captured", final
    print(f"5. ledger state: {final['state']} ✓")

    forged = client.post(
        "/api/webhooks/razorpay",
        content=payload,
        headers={
            **headers,
            "X-Razorpay-Signature": "0" * 64,
            "X-Razorpay-Event-Id": "evt_forged",
        },
    )
    assert forged.status_code == 401
    print("6. forged signature rejected with 401 ✓")
    print("\nE2E PASSED")


if __name__ == "__main__":
    main()
