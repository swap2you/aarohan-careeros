"""Database-backed session authentication tests."""

from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.session_auth import SESSION_COOKIE

LOGIN = {"email": "admin@test.local", "password": "SecurePass123!"}


def _login(client: TestClient, *, remember_me: bool = True) -> None:
    response = client.post(
        "/api/auth/login",
        json={**LOGIN, "remember_me": remember_me},
    )
    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert SESSION_COOKIE in response.cookies


def test_valid_session(client: TestClient):
    _login(client)
    session = client.get("/api/auth/session")
    assert session.status_code == 200
    body = session.json()
    assert body["authenticated"] is True
    assert body["email"] == LOGIN["email"]
    assert body["remember_me"] is True
    assert client.get("/api/analytics").status_code == 200


def test_expired_session(client: TestClient):
    _login(client)
    future = datetime.utcnow() + timedelta(days=400)
    with patch("app.services.session_auth.datetime") as mock_dt:
        mock_dt.utcnow.return_value = future
        expired = client.get("/api/auth/session")
    assert expired.json()["authenticated"] is False
    assert client.get("/api/analytics").status_code == 401


def test_revoked_session_after_logout(client: TestClient):
    _login(client)
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/session").json()["authenticated"] is False
    assert client.get("/api/jobs").status_code == 401


def test_malformed_session_cookie(client: TestClient):
    client.cookies.set(SESSION_COOKIE, "not-a-valid-session-token")
    assert client.get("/api/auth/session").json()["authenticated"] is False
    assert client.get("/api/analytics").status_code == 401


def test_remember_me_flag(client: TestClient):
    _login(client, remember_me=True)
    assert client.get("/api/auth/session").json()["remember_me"] is True


def test_non_remembered_session(client: TestClient):
    _login(client, remember_me=False)
    body = client.get("/api/auth/session").json()
    assert body["authenticated"] is True
    assert body["remember_me"] is False


def test_session_survives_new_client_same_store(client: TestClient):
    _login(client)
    cookies = dict(client.cookies)
    with TestClient(app) as client2:
        for name, value in cookies.items():
            client2.cookies.set(name, value)
        session = client2.get("/api/auth/session")
        assert session.json()["authenticated"] is True
        assert client2.get("/api/jobs").status_code == 200


def test_business_rule_403_does_not_invalidate_session(client: TestClient):
    _login(client)
    res = client.post("/api/applications/submit", json={"mode": "AUTONOMOUS", "application_id": 1})
    assert res.status_code == 403
    assert client.get("/api/auth/session").json()["authenticated"] is True


def test_tampered_session_cookie(client: TestClient):
    _login(client)
    client.cookies.set(SESSION_COOKIE, "tampered-" + "x" * 40)
    assert client.get("/api/auth/session").json()["authenticated"] is False


def test_logout_clears_session(client: TestClient):
    _login(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/session").json()["authenticated"] is False
