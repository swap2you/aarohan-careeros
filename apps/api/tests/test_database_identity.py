"""Database identity marker guards."""

import os

import pytest

from app.services.database_identity import (
    E2E_RUNTIME_USER,
    OWNER_RUNTIME_USER,
    assert_connection_matches_identity,
    assert_owner_runtime_not_testing,
    assert_test_infrastructure,
    identity_purpose,
)


def test_owner_runtime_blocks_pytest(monkeypatch):
    monkeypatch.setenv("AAROHAN_RUNTIME_PROFILE", "owner")
    with pytest.raises(RuntimeError, match="owner runtime"):
        assert_owner_runtime_not_testing()


def test_e2e_identity_rejects_owner_postgres_host(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "E2E")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    with pytest.raises(RuntimeError, match="owner postgres host"):
        assert_connection_matches_identity(
            f"postgresql+psycopg://{E2E_RUNTIME_USER}:secret@postgres:5432/career_os_e2e"
        )


def test_e2e_identity_rejects_owner_runtime_user_on_e2e_db(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "E2E")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    with pytest.raises(RuntimeError, match="must use"):
        assert_connection_matches_identity(
            f"postgresql+psycopg://{OWNER_RUNTIME_USER}:secret@postgres-e2e:5432/career_os_e2e"
        )


def test_e2e_identity_accepts_bootstrap_user_for_provisioning(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "E2E")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    from app.services.database_identity import E2E_BOOTSTRAP_USER

    assert_connection_matches_identity(
        f"postgresql+psycopg://{E2E_BOOTSTRAP_USER}:secret@127.0.0.1:5433/career_os_e2e"
    )


def test_e2e_identity_accepts_isolated_stack_url(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "E2E")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    assert_connection_matches_identity(
        f"postgresql+psycopg://{E2E_RUNTIME_USER}:secret@postgres-e2e:5432/career_os_e2e"
    )


def test_ci_identity_accepts_ephemeral_runtime_url(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "CI")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    assert_connection_matches_identity(
        f"postgresql+psycopg://{OWNER_RUNTIME_USER}:secret@localhost:5432/career_os"
    )


def test_test_infrastructure_requires_e2e_or_ci(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "OWNER")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    with pytest.raises(RuntimeError, match="must be E2E or CI"):
        assert_test_infrastructure("schema reset")


def test_identity_purpose_from_env(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "CI")
    assert identity_purpose() == "CI"
