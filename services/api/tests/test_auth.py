from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import COOKIE_NAME, hash_token, utc_now
from app.main import app
from app.models.entities import AuthSession


def sign_in(client, account):
    user, password = account
    response = client.post(
        "/api/v1/auth/login", json={"login_name": user.login_name, "password": password}
    )
    assert response.status_code == 200
    return response


def test_mock_browser_server_rejects_operator_login_and_existing_operator_cookie(
    accounts, clients, monkeypatch, db
):
    client = clients[0]
    monkeypatch.setenv("UI_TEST_MODE", "true")
    get_settings.cache_clear()
    user, password = accounts[0]
    assert client.get("/api/v1/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login", json={"login_name": user.login_name, "password": password}
        ).status_code
        == 401
    )
    user.login_name = "ui_a"
    db.flush()
    assert sign_in(client, accounts[0]).status_code == 200
    assert client.get("/api/v1/me").json()["login_name"] == "ui_a"


def test_login_cookie_hash_and_identity(accounts, db):
    client = TestClient(app)
    response = sign_in(client, accounts[0])
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "password" not in response.text
    assert "token" not in response.json()
    token = client.cookies.get(COOKIE_NAME)
    assert db.scalar(
        select(AuthSession.token_hash).where(AuthSession.user_id == accounts[0][0].id)
    ) == hash_token(token)
    assert client.get("/api/v1/me").json()["id"] == accounts[0][0].id


def test_incorrect_and_nonexistent_login_have_same_error(accounts):
    client = TestClient(app)
    errors = []
    for name in [accounts[0][0].login_name, "synthetic-does-not-exist"]:
        response = client.post(
            "/api/v1/auth/login", json={"login_name": name, "password": "incorrect"}
        )
        assert response.status_code == 401
        error = response.json()["error"]
        errors.append((error["code"], error["message"]))
    assert errors[0] == errors[1]


def test_expired_and_forged_sessions_rejected(accounts, db):
    client = TestClient(app)
    sign_in(client, accounts[0])
    session = db.scalar(select(AuthSession).where(AuthSession.user_id == accounts[0][0].id))
    session.expires_at = utc_now() - timedelta(seconds=1)
    db.flush()
    assert client.get("/api/v1/me").status_code == 401
    forged = TestClient(app, cookies={COOKIE_NAME: "forged-" + "x" * 36})
    assert forged.get("/api/v1/me").status_code == 401


def test_logout_revokes_copied_cookie(accounts):
    client = TestClient(app)
    sign_in(client, accounts[0])
    copied = client.cookies.get(COOKIE_NAME)
    assert client.post("/api/v1/auth/logout").status_code == 204
    replay = TestClient(app, cookies={COOKIE_NAME: copied})
    assert replay.get("/api/v1/me").status_code == 401


def test_b_cannot_select_a_by_user_id(accounts):
    a, b = TestClient(app), TestClient(app)
    sign_in(a, accounts[0])
    sign_in(b, accounts[1])
    response = b.get("/api/v1/me", params={"user_id": accounts[0][0].id})
    assert response.json()["id"] == accounts[1][0].id
    assert accounts[0][0].login_name not in response.text


def test_disabled_account_denied(accounts, db):
    user, _ = accounts[0]
    user.disabled_at = utc_now()
    db.flush()
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={
            "login_name": user.login_name,
            "password": accounts[0][1],
        },
    )
    assert response.status_code == 401


def test_cross_origin_mutation_is_denied():
    response = TestClient(app).post(
        "/api/v1/auth/login", json={}, headers={"Origin": "https://untrusted.invalid"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_DENIED"


def test_login_validation_does_not_echo_password():
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={"password": "synthetic-private-password-marker", "user_id": "forged"},
    )
    assert response.status_code == 422
    assert "synthetic-private-password-marker" not in response.text
