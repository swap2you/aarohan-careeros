"""PostgreSQL database identity marker adversarial tests."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from app.database import get_engine
from app.services.database_identity import (
    E2E_RUNTIME_USER,
    OWNER_RUNTIME_USER,
    assert_connection_matches_identity,
    load_database_identity_record,
    validate_database_identity_marker,
    validate_runtime_database,
)

pytestmark = pytest.mark.skipif(
    "postgresql" not in os.environ.get("DATABASE_URL", ""),
    reason="PostgreSQL integration URL required",
)


def test_marker_exists_and_matches_env():
    engine = get_engine()
    record = validate_database_identity_marker(engine)
    assert record.purpose == os.environ["AAROHAN_DB_IDENTITY_PURPOSE"].upper()
    assert record.identity_uuid.lower() == os.environ["AAROHAN_DB_IDENTITY_UUID"].lower()


def test_wrong_uuid_fails_startup(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "22222222-2222-4222-8222-222222222222")
    import app.database as database_module

    database_module._engine = None
    with pytest.raises(RuntimeError, match="UUID mismatch"):
        database_module.get_engine()


def test_owner_api_refuses_e2e_database(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "OWNER")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", os.environ["AAROHAN_DB_IDENTITY_UUID"])
    with pytest.raises(RuntimeError, match="cannot target database"):
        assert_connection_matches_identity(
            f"postgresql+psycopg://{OWNER_RUNTIME_USER}:secret@127.0.0.1:5433/career_os_e2e"
        )


def test_e2e_api_refuses_owner_database(monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "E2E")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", os.environ["AAROHAN_DB_IDENTITY_UUID"])
    with pytest.raises(RuntimeError, match="cannot target database"):
        assert_connection_matches_identity(
            f"postgresql+psycopg://{E2E_RUNTIME_USER}:secret@127.0.0.1:5432/career_os"
        )


def test_password_spoof_cannot_bypass_marker():
    with pytest.raises(Exception):
        validate_runtime_database(
            f"postgresql+psycopg://{E2E_RUNTIME_USER}:wrong-password@127.0.0.1:5433/career_os_e2e"
        )


def test_renamed_database_still_protected_by_marker():
    engine = get_engine()
    record = load_database_identity_record(engine)
    assert record.purpose in {"OWNER", "E2E", "CI"}
