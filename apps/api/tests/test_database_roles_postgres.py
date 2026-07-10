"""PostgreSQL database role restriction integration tests."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from app.services.database_identity import (
    E2E_RUNTIME_USER,
    OWNER_RUNTIME_USER,
)

pytestmark = pytest.mark.skipif(
    "postgresql" not in os.environ.get("DATABASE_URL", ""),
    reason="PostgreSQL integration URL required",
)


def _runtime_engine():
    url = os.environ["DATABASE_URL"]
    return create_engine(url, pool_pre_ping=True)


def test_runtime_crud_works():
    engine = _runtime_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO users (email, hashed_password, is_active, is_admin, created_at)
                VALUES ('role-crud@test.local', 'hash', true, false, NOW())
                """
            )
        )
        user_id = conn.execute(
            text("SELECT id FROM users WHERE email = 'role-crud@test.local'")
        ).scalar()
        conn.execute(
            text("UPDATE users SET is_admin = false WHERE id = :id"),
            {"id": user_id},
        )
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE TABLE role_guard_should_fail (id int)",
        "DROP TABLE jobs",
        "DROP SCHEMA public CASCADE",
        "ALTER TABLE jobs ADD COLUMN role_guard_col text",
    ],
)
def test_runtime_cannot_run_ddl(ddl: str):
    engine = _runtime_engine()
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(ddl))


def test_runtime_cannot_modify_identity_marker():
    engine = _runtime_engine()
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE aarohan_meta.database_identity
                    SET purpose = 'SPOOF' WHERE id = 1
                    """
                )
            )


def test_runtime_role_name_matches_purpose():
    url = os.environ["DATABASE_URL"]
    purpose = os.environ.get("AAROHAN_DB_IDENTITY_PURPOSE", "").upper()
    if purpose == "OWNER":
        assert OWNER_RUNTIME_USER in url
    elif purpose == "E2E":
        assert E2E_RUNTIME_USER in url
