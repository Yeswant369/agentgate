from fastapi.testclient import TestClient

from gateway.main import create_app


def test_404_returns_problem_json(client):
    resp = client.get("/api/nope")
    assert resp.status_code == 404
    body = resp.json()
    assert body["status"] == 404
    assert "request_id" in body
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_unhandled_exception_returns_500_without_traceback():
    app = create_app()

    @app.get("/api/_boom")
    def boom():
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/_boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["title"] == "Internal server error"
    assert "secret internal detail" not in resp.text
    assert "request_id" in body
