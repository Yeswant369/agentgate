def test_liveness_is_up_regardless_of_dependencies(client):
    resp = client.get("/api/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "live"


def test_readiness_fails_without_database(client, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    resp = client.get("/api/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["title"] == "Not ready"
    assert resp.headers["content-type"].startswith("application/problem+json")
