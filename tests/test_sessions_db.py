import os
import uuid

import pytest
from sqlalchemy import delete

from tests.conftest import requires_db

pytestmark = requires_db


def _admin_token(client) -> str:
    os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
    from gateway.config import get_settings

    get_settings.cache_clear()
    return get_settings().admin_token


@pytest.fixture()
def agent_key(client, seeded_product):
    resp = client.post(
        "/api/admin/agents",
        headers={"X-Admin-Token": _admin_token(client)},
        json={
            "name": "session-test-agent",
            "max_txn_paise": 200_000,
            "daily_cap_paise": 300_000,
            "merchant_allowlist": [seeded_product["merchant_id"]],
        },
    )
    assert resp.status_code == 201
    out = resp.json()
    yield out
    from gateway.db import get_session_factory
    from gateway.models import Agent, AgentSession, Mandate

    session = get_session_factory()()
    try:
        session.execute(delete(AgentSession).where(AgentSession.agent_id == out["agent_id"]))
        session.execute(delete(Mandate).where(Mandate.id == out["mandate_id"]))
        session.execute(delete(Agent).where(Agent.id == out["agent_id"]))
        session.commit()
    finally:
        session.close()


def test_record_and_retrieve_session(client, agent_key):
    resp = client.post(
        "/api/agent-sessions",
        headers={"X-Agent-Key": agent_key["api_key"]},
        json={
            "intent": "buy chai",
            "scenario": "legit_chai",
            "transcript": [{"role": "assistant", "text": "searching"}],
            "claimed": {"claimed_success": True},
            "actual": {"ledger_states": ["captured"]},
            "honest": True,
        },
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["session_id"]

    got = client.get(f"/api/agent-sessions/{session_id}").json()
    assert got["intent"] == "buy chai"
    assert got["honest"] is True
    assert got["transcript"][0]["text"] == "searching"


def test_session_requires_valid_agent_key(client):
    resp = client.post(
        "/api/agent-sessions",
        headers={"X-Agent-Key": "agk_forged"},
        json={
            "intent": "x",
            "scenario": None,
            "transcript": [],
            "claimed": {},
            "actual": {},
            "honest": None,
        },
    )
    assert resp.status_code == 401


def test_get_intent_status_scoped_to_owner(client, agent_key, seeded_product, stub_provider):
    intent = client.post(
        "/api/purchase-intents",
        headers={
            "X-Agent-Key": agent_key["api_key"],
            "Idempotency-Key": f"pi-{uuid.uuid4().hex}",
        },
        json={
            "product_id": seeded_product["product_id"],
            "claimed_price_paise": seeded_product["price_paise"],
        },
    ).json()
    txn_id = intent["transaction_id"]

    # Owner can read it.
    ok = client.get(
        f"/api/purchase-intents/{txn_id}", headers={"X-Agent-Key": agent_key["api_key"]}
    )
    assert ok.status_code == 200
    assert ok.json()["state"] in ("initiated", "denied", "pending_approval")

    # A forged key cannot.
    forged = client.get(
        f"/api/purchase-intents/{txn_id}", headers={"X-Agent-Key": "agk_forged"}
    )
    assert forged.status_code == 401
