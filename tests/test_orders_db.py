import uuid

from tests.conftest import requires_db

pytestmark = requires_db


def test_create_order_prices_from_catalog_not_request(client, seeded_product, stub_provider):
    resp = client.post(
        "/api/orders",
        json={"product_id": seeded_product["product_id"]},
        headers={"Idempotency-Key": f"key-{uuid.uuid4().hex}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["amount_paise"] == seeded_product["price_paise"]
    assert body["state"] == "initiated"
    assert body["razorpay_order_id"].startswith("order_stub_")
    assert body["idempotent_replay"] is False


def test_same_idempotency_key_returns_original_not_second_charge(
    client, seeded_product, stub_provider
):
    key = f"key-{uuid.uuid4().hex}"
    first = client.post(
        "/api/orders",
        json={"product_id": seeded_product["product_id"]},
        headers={"Idempotency-Key": key},
    ).json()
    second = client.post(
        "/api/orders",
        json={"product_id": seeded_product["product_id"]},
        headers={"Idempotency-Key": key},
    )
    assert second.status_code == 201
    replay = second.json()
    assert replay["transaction_id"] == first["transaction_id"]
    assert replay["idempotent_replay"] is True


def test_missing_idempotency_key_rejected(client, seeded_product, stub_provider):
    resp = client.post("/api/orders", json={"product_id": seeded_product["product_id"]})
    assert resp.status_code == 422


def test_unknown_product_404(client, stub_provider):
    resp = client.post(
        "/api/orders",
        json={"product_id": "p_does_not_exist"},
        headers={"Idempotency-Key": f"key-{uuid.uuid4().hex}"},
    )
    assert resp.status_code == 404
