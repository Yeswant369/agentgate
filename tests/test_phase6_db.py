from tests.conftest import requires_db

pytestmark = requires_db


def test_overview_counters(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert "total_decisions" in body
    assert "chain" in body and "intact" in body["chain"]


def test_playground_scenarios_listed(client):
    r = client.get("/api/playground/scenarios")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert {"legit_purchase", "prompt_injection_price", "structuring_attack"} <= ids


def test_playground_replay_is_live_and_correct(client):
    # legit -> allow, injection -> deny, computed live by the real engine.
    legit = client.post("/api/playground/replay/legit_purchase").json()
    assert legit["decision"] == "allow"
    assert legit["matches_expected"] is True

    inj = client.post("/api/playground/replay/prompt_injection_price").json()
    assert inj["decision"] == "deny"
    assert any(r["rule_id"] == "price_integrity" for r in inj["rules"])


def test_playground_unknown_scenario_404(client):
    r = client.post("/api/playground/replay/nope")
    assert r.status_code == 404


def test_audit_export_shape(client):
    r = client.get("/api/audit/export?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["genesis_hash"] == "0" * 64
    assert "records" in body
    if body["records"]:
        rec = body["records"][0]
        assert {"id", "hash", "prev_hash", "rule_results"} <= set(rec)
