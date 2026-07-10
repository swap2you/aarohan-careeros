"""Guardrails: postgres schema reset must never wipe owner career_os."""

import pytest
from sqlalchemy.engine import make_url

from app.services.database_identity import E2E_RUNTIME_USER, OWNER_RUNTIME_USER
from tests.postgres_utils import assert_safe_to_reset_database


def test_owner_career_os_url_is_rejected():
    with pytest.raises(RuntimeError, match="Refusing to reset"):
        assert_safe_to_reset_database(
            "postgresql+psycopg://career_os:secret@postgres:5432/career_os"
        )


def test_e2e_database_is_allowed(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "E2E")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    url = assert_safe_to_reset_database(
        f"postgresql+psycopg://{E2E_RUNTIME_USER}:secret@postgres-e2e:5432/career_os_e2e"
    )
    assert url.endswith("career_os_e2e")


def test_ci_ephemeral_runtime_career_os_is_allowed(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "CI")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    url = assert_safe_to_reset_database(
        f"postgresql+psycopg://{OWNER_RUNTIME_USER}:testruntime@localhost:5432/career_os"
    )
    assert url.endswith("/career_os")


def test_ci_bootstrap_credentials_are_rejected(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "CI")
    with pytest.raises(RuntimeError, match="bootstrap credentials"):
        assert_safe_to_reset_database(
            "postgresql+psycopg://career_os:testpass@localhost:5432/career_os"
        )


def test_redacted_engine_url_still_blocked_without_env():
    # SQLAlchemy often stringifies passwords as *** — must not allow wipe via that alone.
    with pytest.raises(RuntimeError, match="Refusing to reset"):
        assert_safe_to_reset_database(
            "postgresql+psycopg://career_os:***@localhost:5432/career_os"
        )


def test_named_test_database_is_allowed(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "E2E")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    url = assert_safe_to_reset_database(
        f"postgresql+psycopg://{E2E_RUNTIME_USER}:secret@postgres-e2e:5432/career_os_test"
    )
    assert make_url(url.replace("postgresql+psycopg://", "postgresql://")).database == "career_os_test"
