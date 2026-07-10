"""Environment isolation — owner vs E2E account scoping."""

import pytest
from fastapi.testclient import TestClient

from app.services.environment import E2E_TEST_EMAIL, assert_e2e_user_allowed, deployment_badge


def test_e2e_login_blocked_on_owner_stack(client: TestClient):
    from app.config import settings

    if settings.database_url and "career_os_e2e" in settings.database_url:
        pytest.skip("SQLite/E2E DB in test harness")
    if (settings.aarohan_db_identity_purpose or "").upper() == "CI":
        pytest.skip("CI identity database is not the owner stack")
    with pytest.raises(PermissionError):
        assert_e2e_user_allowed(E2E_TEST_EMAIL)


def test_login_rejects_e2e_on_owner(client: TestClient):
    from app.config import settings

    if settings.database_url and "career_os_e2e" in settings.database_url:
        pytest.skip("E2E database")
    if (settings.aarohan_db_identity_purpose or "").upper() == "CI":
        pytest.skip("CI identity database is not the owner stack")
    response = client.post(
        "/api/auth/login",
        json={"email": E2E_TEST_EMAIL, "password": "wrong-password-but-checked-after-email"},
    )
    assert response.status_code == 403
    assert "E2E" in response.json()["detail"]


def test_environment_endpoint(client: TestClient, auth_headers):
    response = client.get("/api/environment", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["badge"] in {"OWNER LOCAL", "E2E TEST", "FIXTURE"}
    assert "database" in body


def test_deployment_badge_owner_in_tests():
    assert deployment_badge() in {"OWNER LOCAL", "E2E TEST", "FIXTURE"}
