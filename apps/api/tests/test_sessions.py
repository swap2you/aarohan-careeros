"""R2.6.1 database session lifecycle tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserSession
from app.services.sessions import SESSION_COOKIE_NAME, hash_session_token


def _login(client: TestClient, *, remember_me: bool = True) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@test.local", "password": "SecurePass123!", "remember_me": remember_me},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _session_row(db: Session, raw_token: str) -> UserSession | None:
    return (
        db.query(UserSession)
        .filter(UserSession.session_token_hash == hash_session_token(raw_token))
        .one_or_none()
    )


def test_valid_session_cookie_and_endpoint(client: TestClient):
    raw = _login(client)
    session = client.get("/api/auth/session")
    assert session.status_code == 200
    body = session.json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == "admin@test.local"
    assert body["remember_me"] is True

    me = client.get("/api/auth/me")
    assert me.status_code == 200


def test_valid_session_bearer_fallback(client: TestClient):
    raw = _login(client)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert response.status_code == 200


def test_unauthenticated_returns_401_with_header(client: TestClient):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers.get("X-Aarohan-Auth") == "session-required"


def test_malformed_session_cookie_rejected(client: TestClient):
    client.cookies.set(SESSION_COOKIE_NAME, "not-a-valid-session-token")
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    session = client.get("/api/auth/session")
    assert session.json()["authenticated"] is False


def test_expired_session_rejected(client: TestClient):
    raw = _login(client)
    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)
    row = _session_row(db, raw)
    assert row is not None
    row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.add(row)
    db.commit()

    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers.get("X-Aarohan-Auth") == "session-required"


def test_revoked_session_rejected(client: TestClient):
    raw = _login(client)
    logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {raw}"})
    assert logout.status_code == 200
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert response.status_code == 401


def test_logout_revokes_server_session(client: TestClient):
    raw = _login(client)
    override = client.app.dependency_overrides[get_db]

    def inspect_db():
        gen = override()
        db = next(gen)
        row = _session_row(db, raw)
        assert row is not None
        assert row.revoked_at is None
        yield db
        try:
            next(gen)
        except StopIteration:
            pass

    client.app.dependency_overrides[get_db] = inspect_db
    try:
        client.post("/api/auth/logout", headers={"Authorization": f"Bearer {raw}"})
    finally:
        client.app.dependency_overrides[get_db] = override

    gen = override()
    db = next(gen)
    row = _session_row(db, raw)
    assert row is not None
    assert row.revoked_at is not None


def test_remember_me_flag_stored(client: TestClient):
    raw = _login(client, remember_me=True)
    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)
    row = _session_row(db, raw)
    assert row is not None
    assert row.remember_me is True
    assert row.expires_at > datetime.utcnow() + timedelta(days=30)


def test_non_remember_session_shorter_ttl(client: TestClient):
    raw = _login(client, remember_me=False)
    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)
    row = _session_row(db, raw)
    assert row is not None
    assert row.remember_me is False
    delta = row.expires_at - datetime.utcnow()
    assert delta < timedelta(days=2)


def test_session_survives_new_request_context(client: TestClient):
    raw = _login(client)
    client.cookies.clear()
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert response.status_code == 200


def test_business_rule_403_not_auth_header(client: TestClient, auth_headers):
    response = client.post(
        "/api/applications/99999/actions",
        headers=auth_headers,
        json={"action": "mark_submitted"},
    )
    assert response.status_code in {403, 404}
    assert response.headers.get("X-Aarohan-Auth") != "session-required"


def test_cleanup_expired_sessions_on_login(client: TestClient):
    raw = _login(client)
    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)
    row = _session_row(db, raw)
    assert row is not None
    row.expires_at = datetime.utcnow() - timedelta(hours=1)
    row.revoked_at = None
    db.add(row)
    db.commit()

    _login(client)
    db.expire_all()
    refreshed = db.query(UserSession).filter(UserSession.id == row.id).one()
    assert refreshed.revoked_at is not None
