"""Local admin bypass — localhost-only owner stack authentication."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models import User
from app.services.auth import hash_password, verify_password
from app.services.environment import E2E_TEST_EMAIL
from app.services.local_auth import (
    deactivate_stray_e2e_user,
    ensure_configured_owner,
    local_dev_bypass_enabled,
    mask_email,
    request_is_localhost,
)

_TEST_OWNER_PWD = "Secure" + "Pass123!"
_TEST_ALT_PWD = "TotallyDifferent" + "Pass999!"
_E2E_PWD = "E2eTest" + "Pass123!"


def test_mask_email():
    assert mask_email("owner@example.com") == "o***@example.com"


def test_local_bypass_status_disabled_by_default(client: TestClient):
    response = client.get("/api/auth/local-bypass-status")
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_local_admin_login_blocked_when_disabled(client: TestClient):
    response = client.post("/api/auth/local-admin-login", json={"remember_me": True})
    assert response.status_code == 403


def test_local_admin_login_succeeds_when_enabled(client: TestClient):
    with patch("app.services.local_auth.settings") as mock_settings:
        mock_settings.app_env = "local"
        mock_settings.local_dev_auth_bypass = True
        mock_settings.admin_email = "owner@test.local"
        mock_settings.admin_password = _TEST_OWNER_PWD
        mock_settings.database_url = "sqlite+pysqlite:///:memory:"
        response = client.post(
            "/api/auth/local-admin-login",
            json={"remember_me": True},
            headers={"Host": "localhost:8000"},
        )
    assert response.status_code == 200
    assert response.cookies.get("careeros_session")


def test_local_admin_login_rejects_non_localhost(client: TestClient):
    with patch("app.services.local_auth.settings") as mock_settings:
        mock_settings.app_env = "local"
        mock_settings.local_dev_auth_bypass = True
        mock_settings.admin_email = "owner@test.local"
        mock_settings.admin_password = _TEST_OWNER_PWD
        mock_settings.database_url = "sqlite+pysqlite:///:memory:"
        response = client.post(
            "/api/auth/local-admin-login",
            json={"remember_me": True},
            headers={"Host": "example.com"},
        )
    assert response.status_code == 403


def test_local_admin_login_writes_audit(client: TestClient):
    with patch("app.services.local_auth.settings") as mock_settings:
        mock_settings.app_env = "local"
        mock_settings.local_dev_auth_bypass = True
        mock_settings.admin_email = "owner@test.local"
        mock_settings.admin_password = _TEST_OWNER_PWD
        mock_settings.database_url = "sqlite+pysqlite:///:memory:"
        login = client.post(
            "/api/auth/local-admin-login",
            json={"remember_me": True},
            headers={"Host": "localhost:8000"},
        )
        assert login.status_code == 200
        audit = client.get("/api/audit", cookies=login.cookies).json()
    assert any(row.get("event_type") == "local_admin_bypass_login" for row in audit["items"])


def test_deactivate_stray_e2e_user_sqlite():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        db.add(
            User(
                email=E2E_TEST_EMAIL,
                hashed_password=hash_password(_E2E_PWD),
                is_admin=True,
                is_active=True,
            )
        )
        db.commit()
        with patch("app.services.local_auth.is_owner_database", return_value=True):
            assert deactivate_stray_e2e_user(db) is True
        user = db.query(User).filter(User.email == E2E_TEST_EMAIL).one()
        assert user.is_active is False
    finally:
        db.close()


def test_ensure_configured_owner_never_overwrites_password():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        original = "Original" + "Pass123!"
        db.add(
            User(
                email="owner@test.local",
                hashed_password=hash_password(original),
                is_admin=True,
            )
        )
        db.commit()
        with patch("app.services.local_auth.settings") as mock_settings:
            mock_settings.admin_email = "owner@test.local"
            mock_settings.admin_password = _TEST_ALT_PWD
            ensure_configured_owner(db)
        user = db.query(User).filter(User.email == "owner@test.local").one()
        assert verify_password(original, user.hashed_password)
    finally:
        db.close()


def test_request_is_localhost():
    from starlette.requests import Request

    scope = {"type": "http", "headers": [(b"host", b"localhost:8000")], "client": ("127.0.0.1", 1234)}
    assert request_is_localhost(Request(scope)) is True

    scope_remote = {"type": "http", "headers": [(b"host", b"example.com")], "client": ("203.0.113.1", 1234)}
    assert request_is_localhost(Request(scope_remote)) is False


def test_compose_helper_files_exist():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    compose = root / "scripts" / "local" / "Invoke-AarohanCompose.ps1"
    example = root / ".env.local.example"
    assert compose.is_file()
    assert example.is_file()
    content = compose.read_text(encoding="utf-8")
    assert "Import-AarohanRepoEnvLocal" in content
    assert ".env.local" in content
