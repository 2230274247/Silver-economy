import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_and_request_id():
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(response.headers["X-Request-ID"]) == 36


def test_database_unavailable_is_sanitized(monkeypatch):
    def unavailable():
        raise ValueError("synthetic-private-connection-value")

    monkeypatch.setattr("app.main.get_engine", unavailable)
    response = client.get("/api/v1/readyz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "synthetic-private" not in response.text


def test_request_logs_exclude_body(caplog):
    with caplog.at_level(logging.INFO, logger="silver.api"):
        response = client.post("/not-implemented", json={"content": "synthetic-sensitive-marker"})
    assert response.status_code == 404
    assert "synthetic-sensitive-marker" not in caplog.text
    assert "request_id=" in caplog.text
