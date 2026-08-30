def test_liveness_is_up_regardless_of_dependencies(client):
    resp = client.get("/api/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "live"


def test_readiness_fails_when_database_unreachable(client, monkeypatch):
    import gateway.routes.health as health_module

    def broken_db_check():
        raise ConnectionError("db is down")

    monkeypatch.setattr(health_module, "check_database_ready", broken_db_check)
    resp = client.get("/api/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["title"] == "Not ready"
    assert resp.headers["content-type"].startswith("application/problem+json")
