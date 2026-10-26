from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_service_reports_actual_stage_without_credentials():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "service": "silver-memory-api",
        "stage": "chat",
        "provider": "mock",
    }


def test_unimplemented_business_endpoint_is_not_fake_success():
    assert client.post("/api/v1/outing-tasks", json={}).status_code == 404


def test_openapi_is_available():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["version"] == "0.1.0-alpha"
