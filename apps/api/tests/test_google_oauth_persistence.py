"""Google OAuth token persistence tests."""

from unittest.mock import MagicMock, patch

from app.models import OAuthToken
from app.services.crypto import decrypt_payload, encrypt_payload
from app.services.google_api import get_token, save_token


def _mock_db_with_row(row):
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value.all.return_value = [row] if row else []
    query.filter.return_value.first.return_value = row
    query.filter.return_value.one_or_none.return_value = row
    db.query.return_value = query
    return db


def test_save_token_preserves_refresh_when_missing():
    prior = {"access_token": "old-access", "refresh_token": "keep-me", "expires_in": 3600}
    existing = OAuthToken(
        provider="google",
        service="google",
        encrypted_token=encrypt_payload(prior),
        is_active=True,
    )
    db = _mock_db_with_row(existing)
    new_data = {"access_token": "new-access", "expires_in": 3600}
    save_token(db, service="google", token_data=new_data, account_email="user@example.com")
    added = db.add.call_args[0][0]
    stored = decrypt_payload(added.encrypted_token)
    assert stored["refresh_token"] == "keep-me"
    assert stored["access_token"] == "new-access"


def test_integration_status_never_exposes_tokens(client, auth_headers):
    response = client.get("/api/integrations/status", headers=auth_headers)
    assert response.status_code == 200
    payload = response.text.lower()
    assert "refresh_token" not in payload
    assert "access_token" not in payload


def test_get_token_marks_reconnect_on_refresh_failure():
    from datetime import datetime, timedelta

    from app.services.crypto import encrypt_payload
    from app.services.google_api import get_token

    prior = {
        "access_token": "expired",
        "refresh_token": "bad",
        "expires_in": 0,
    }
    row = OAuthToken(
        provider="google",
        service="google",
        encrypted_token=encrypt_payload(prior),
        is_active=True,
        expires_at=datetime.utcnow() - timedelta(minutes=5),
        connection_status="connected",
    )
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value.order_by.return_value.first.return_value = row
    db.query.return_value = query

    with patch("app.services.google_api.settings") as mock_settings:
        mock_settings.oauth_fixture_mode = False
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value.status_code = 400
            mock_client.return_value.__enter__.return_value.post.return_value.text = "invalid_grant"
            result = get_token(db, "google")
    assert result is None
    assert row.connection_status == "reconnect_required"
