"""Google OAuth token persistence for R2.6.1."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.database import get_db
from app.models import OAuthToken
from app.services.google_api import _refresh_access_token, get_token, save_token
from app.services.crypto import decrypt_payload, encrypt_payload


def test_save_token_preserves_refresh_when_missing(client: TestClient, auth_headers):
    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)

    save_token(
        db,
        service="google",
        token_data={"access_token": "a1", "refresh_token": "r1", "expires_in": 3600},
        account_email="user@example.com",
        scopes=["openid"],
    )
    save_token(
        db,
        service="google",
        token_data={"access_token": "a2", "expires_in": 3600},
        account_email="user@example.com",
        scopes=["openid"],
    )
    active = (
        db.query(OAuthToken)
        .filter(
            OAuthToken.provider == "google",
            OAuthToken.service == "google",
            OAuthToken.is_active.is_(True),
        )
        .order_by(OAuthToken.id.desc())
        .first()
    )
    stored = decrypt_payload(active.encrypted_token)
    assert stored["refresh_token"] == "r1"
    assert stored["access_token"] == "a2"

    status = client.get("/api/integrations/status", headers=auth_headers)
    assert status.status_code == 200
    assert "refresh_token" not in status.text
    assert "access_token" not in status.text


def test_refresh_keeps_refresh_token():
    db = MagicMock()
    row = OAuthToken(
        provider="google",
        service="google",
        account_email="user@example.com",
        encrypted_token=encrypt_payload({"access_token": "old", "refresh_token": "r1"}),
        scopes="openid",
        expires_at=datetime.utcnow() - timedelta(minutes=5),
        is_active=True,
    )
    mock_response = httpx.Response(200, json={"access_token": "new", "expires_in": 3600})
    with patch("app.services.google_api.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        refreshed = _refresh_access_token(db, row, decrypt_payload(row.encrypted_token))
    assert refreshed["refresh_token"] == "r1"
    assert refreshed["access_token"] == "new"


def test_get_token_auto_refresh_when_expired():
    db = MagicMock()
    expired = {
        "access_token": "old",
        "refresh_token": "r1",
        "expires_in": -60,
    }
    row = OAuthToken(
        provider="google",
        service="google",
        account_email="user@example.com",
        encrypted_token=encrypt_payload(expired),
        scopes="openid",
        expires_at=datetime.utcnow() - timedelta(minutes=1),
        is_active=True,
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
    with (
        patch("app.services.google_api.settings") as mock_settings,
        patch(
            "app.services.google_api._refresh_access_token",
            return_value={**expired, "access_token": "new"},
        ) as mock_refresh,
    ):
        mock_settings.oauth_fixture_mode = False
        token = get_token(db, "google")
    assert token is not None
    assert token["access_token"] == "new"
    mock_refresh.assert_called_once()


def test_tokens_not_in_integration_status_payload(client: TestClient, auth_headers):
    response = client.get("/api/integrations/status", headers=auth_headers)
    assert response.status_code == 200
    text = response.text.lower()
    assert "refresh_token" not in text
    assert "access_token" not in text
