"""Shared helpers for PostgreSQL integration tests."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from sqlalchemy import Engine, text
from sqlalchemy.engine.url import make_url

from app.services.database_identity import (
    PURPOSE_CI,
    PURPOSE_E2E,
    assert_connection_matches_identity,
    identity_purpose,
)

# Databases that may be wiped by integration tests. Never include owner career_os
# unless this is clearly the CI ephemeral service (password testpass) with CI identity.
_ALLOWED_RESET_DB_NAMES = {
    "career_os_e2e",
    "career_os_test",
    "test",
    "postgres_test",
}


def _url_parts(database_url: str) -> tuple[str, str, str]:
    """Return (database_name, password, host) from a SQLAlchemy/psycopg URL."""
    # Prefer SQLAlchemy parsing (handles postgresql+psycopg://)
    try:
        u = make_url(database_url)
        return (u.database or "", u.password or "", u.host or "")
    except Exception:
        parsed = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://", 1))
        db_name = (parsed.path or "").lstrip("/").split("?")[0]
        return db_name, parsed.password or "", parsed.hostname or ""


def assert_safe_to_reset_database(database_url: str | None = None) -> str:
    """Refuse destructive schema resets against the owner database.

    Owner stack uses DATABASE_URL .../career_os with a real password.
    Integration tests must target an isolated DB (career_os_e2e / career_os_test)
    or CI's ephemeral service DB (password exactly ``testpass``).
    """
    url = database_url or os.environ.get("DATABASE_URL") or ""
    if not url or "postgresql" not in url:
        raise RuntimeError("PostgreSQL DATABASE_URL required for schema reset")

    db_name, password, host = _url_parts(url)

    if db_name in _ALLOWED_RESET_DB_NAMES:
        assert_connection_matches_identity(url)
        return url

    # CI ephemeral postgres service: career_os + CI runtime password (+ localhost/127.0.0.1)
    if db_name == "career_os" and host in {"localhost", "127.0.0.1", "postgres"}:
        purpose = identity_purpose()
        if purpose == PURPOSE_CI:
            if password == "testpass":
                raise RuntimeError(
                    "Refusing CI career_os reset with bootstrap credentials; use runtime role URL."
                )
            assert_connection_matches_identity(url)
            return url
        if password == "testpass":
            raise RuntimeError(
                "Refusing CI career_os reset with bootstrap credentials; use runtime role URL."
            )

    if db_name.endswith("_test") or db_name.endswith("_e2e"):
        assert_connection_matches_identity(url)
        purpose = identity_purpose()
        if purpose and purpose not in {PURPOSE_E2E, PURPOSE_CI}:
            raise RuntimeError(
                f"Refusing to reset PostgreSQL database {db_name!r}: "
                f"identity purpose {purpose!r} is not E2E/CI."
            )
        return url

    raise RuntimeError(
        f"Refusing to reset PostgreSQL database {db_name!r}. "
        "Owner database career_os must never be wiped by tests. "
        "Use career_os_e2e / career_os_test, or set DATABASE_URL to an isolated DB."
    )


def reset_public_schema(engine: Engine, database_url: str | None = None) -> None:
    """Drop and recreate public schema (avoids circular FK drop_all failures)."""
    url = database_url or os.environ.get("DATABASE_URL") or ""
    if url.startswith("postgresql"):
        assert_safe_to_reset_database(url)
    else:
        assert_safe_to_reset_database(engine.url.render_as_string(hide_password=False))
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS aarohan_meta CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
