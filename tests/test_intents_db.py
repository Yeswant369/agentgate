import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import delete, text

from tests.conftest import requires_db

pytestmark = requires_db

# NOTE ON CLEANUP: audit_log rows are NEVER deleted by tests. The chain is
# append-only by design — deleting mid-chain rows would break verification
# forever. Audit rows reference agents/transactions by plain string id, so
# deleting the test agent/transactions leaves the chain fully verifiable.


def _admin_token(client) -> str:
    os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
    from gateway.config import get_settings

    get_settings.cache_clear()
    return get_settings().admin_token


def _create_agent(client, merchant_id: str, daily_cap: int = 300_000) -> dict:
    resp = client.post(
        "/api/admin/agents",
        headers={"X-Admin-Token": _admin_token(client)},
        json={
            "name": "test-agent",
            "max_txn_paise": 200_000,
            "daily_cap_paise": daily_cap,
            "merchant_allowlist": [merchant_id],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _cleanup_agent(out: dict) -> None:
    from gateway.db import get_session_factory
    from gateway.models import Agent, Mandate

    session = get_session_factory()()
    try:
        session.execute(delete(Mandate).where(Mandate.id == out["mandate_id"]))
        session.execute(delete(Agent).where(Agent.id == out["agent_id"]))
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def gated_agent(client, seeded_product):
    out = _create_agent(client, seeded_product["merchant_id"])
    yield {**out, "product": seeded_product}
    _cleanup_agent(out)


def _intent(client, agent, claimed=None, key=None):
    product = agent["product"]
    return client.post(
        "/api/purchase-intents",
        headers={
            "X-Agent-Key": agent["api_key"],
            "Idempotency-Key": key or f"pi-{uuid.uuid4().hex}",
        },
        json={
            "product_id": product["product_id"],
            "claimed_price_paise": claimed or product["price_paise"],
        },
    )


def test_clean_intent_allowed_with_audit(client, gated_agent):
    resp = _intent(client, gated_agent)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["decision"] == "allow"
    assert body["state"] == "initiated"
    assert body["audit_id"] > 0

    detail = client.get(f"/api/decisions/{body['audit_id']}").json()
    assert detail["decision"] == "allow"
    assert len(detail["rule_results"]) >= 9  # every rule ran and was recorded


def test_wrong_claimed_price_denied(client, gated_agent):
    resp = _intent(client, gated_agent, claimed=999)
    body = resp.json()
    assert body["decision"] == "deny"
    assert any(r["rule_id"] == "price_integrity" for r in body["reasons"])
    assert body["state"] == "denied"


def test_invalid_agent_key_rejected(client):
    resp = client.post(
        "/api/purchase-intents",
        headers={"X-Agent-Key": "agk_forged", "Idempotency-Key": f"pi-{uuid.uuid4().hex}"},
        json={"product_id": "p_x", "claimed_price_paise": 1},
    )
    assert resp.status_code == 401


def test_replay_endpoint_reproduces_decision(client, gated_agent):
    body = _intent(client, gated_agent, claimed=999).json()
    replay = client.post(f"/api/decisions/{body['audit_id']}/replay").json()
    assert replay["identical"] is True
    assert replay["replayed_decision"] == "deny"


def test_audit_chain_tamper_detected_then_restored(client, gated_agent):
    """Tamper with a real row, watch verification break, then restore the
    exact original content and watch it verify again."""
    denied = _intent(client, gated_agent, claimed=999).json()
    audit_id = denied["audit_id"]
    assert client.get("/api/audit/verify").json()["intact"] is True

    from gateway.db import get_session_factory

    session = get_session_factory()()
    try:
        session.execute(
            text("UPDATE audit_log SET decision='allow' WHERE id=:i"), {"i": audit_id}
        )
        session.commit()
        assert client.get("/api/audit/verify").json()["intact"] is False
        session.execute(
            text("UPDATE audit_log SET decision='deny' WHERE id=:i"), {"i": audit_id}
        )
        session.commit()
    finally:
        session.close()
    assert client.get("/api/audit/verify").json()["intact"] is True


def test_ten_concurrent_requests_cap_room_for_one(client, seeded_product):
    """THE race test. Daily cap fits exactly one purchase of the test product
    (price 123456, cap 150000). 10 concurrent intents: exactly one allow —
    whether the rest lose to the daily cap or the duplicate rule, none may
    slip through."""
    out = _create_agent(client, seeded_product["merchant_id"], daily_cap=150_000)
    agent = {**out, "product": seeded_product}
    try:

        def fire(_):
            return _intent(client, agent).json()["decision"]

        with ThreadPoolExecutor(max_workers=10) as pool:
            decisions = list(pool.map(fire, range(10)))
        assert decisions.count("allow") == 1, decisions
        assert decisions.count("deny") == 9, decisions
    finally:
        _cleanup_agent(out)


def test_fail_closed_when_policy_engine_breaks(client, gated_agent, monkeypatch):
    import gateway.routes.intents as intents_module

    def broken_gather(*args, **kwargs):
        raise ConnectionError("simulated infrastructure failure")

    monkeypatch.setattr(intents_module, "gather_input", broken_gather)
    resp = _intent(client, gated_agent)
    assert resp.status_code == 503
    assert "denied fail-closed" in resp.json()["detail"]
