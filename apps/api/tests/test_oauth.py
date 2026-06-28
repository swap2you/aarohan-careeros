from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.google_api import DEFAULT_GOOGLE_SCOPES, OAUTH_REMEDIATION, remediation_for_error


def test_oauth_default_scopes():
    assert "openid" in DEFAULT_GOOGLE_SCOPES
    assert "https://www.googleapis.com/auth/gmail.readonly" in DEFAULT_GOOGLE_SCOPES
    assert "https://www.googleapis.com/auth/drive.file" in DEFAULT_GOOGLE_SCOPES
    assert "https://mail.google.com/" not in DEFAULT_GOOGLE_SCOPES


def test_oauth_remediation_messages():
    assert "redirect" in remediation_for_error("redirect_uri_mismatch").lower()
    assert OAUTH_REMEDIATION["wrong_account"]


def test_google_connect_not_configured(client: TestClient, auth_headers):
    with patch("app.routers.integrations.settings") as mock_settings:
        mock_settings.google_client_id = ""
        mock_settings.google_client_secret = ""
        response = client.get("/api/integrations/google/connect", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["configured"] is False


def test_google_connect_returns_auth_url(client: TestClient, auth_headers):
    with patch("app.routers.integrations.settings") as mock_settings:
        mock_settings.google_client_id = "test-client-id"
        mock_settings.google_client_secret = "test-secret"
        mock_settings.google_oauth_redirect_uri = "http://localhost:8000/api/integrations/google/callback"
        mock_settings.enable_external_email_send = False
        with patch("app.services.google_api.settings", mock_settings):
            response = client.get("/api/integrations/google/connect", headers=auth_headers)
    body = response.json()
    assert "auth_url" in body
    assert "test-client-id" in body["auth_url"]
    assert "gmail.readonly" in body["auth_url"]


def test_google_callback_invalid_state(client: TestClient):
    response = client.get("/api/integrations/google/callback?code=x&state=bad")
    assert response.status_code == 400


def test_gmail_test_send_generates_eml(client: TestClient, auth_headers):
    response = client.post(
        "/api/integrations/gmail/test-send",
        headers=auth_headers,
        params={"to": "swap2you@gmail.com", "subject": "Hello", "body": "Test", "confirm": False},
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "eml"
