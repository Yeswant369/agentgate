def test_response_carries_generated_request_id(client):
    resp = client.get("/api/health/live")
    rid = resp.headers.get("X-Request-ID")
    assert rid and len(rid) == 32


def test_incoming_request_id_is_honored(client):
    resp = client.get("/api/health/live", headers={"X-Request-ID": "trace-abc-123"})
    assert resp.headers["X-Request-ID"] == "trace-abc-123"
