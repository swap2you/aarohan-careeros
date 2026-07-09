"""Shared helpers for PostgreSQL integration tests."""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from sqlalchemy import Engine, text

# Databases that may be wiped by integration tests. Never include owner career_os.
_ALLOWED_RESET_DB_NAMES = {
    "career_os_e2e",
    "career_os_test",
    "test",
    "postgres_test",
}


def assert_safe_to_reset_database(database_url: str | None = None) -> str:
    """Refuse destructive schema resets against the owner database.

    Owner stack uses DATABASE_URL .../career_os. Integration tests must target
    an isolated DB (career_os_e2e / career_os_test) or CI's ephemeral service DB.
    """
    url = database_url or os.environ.get("DATABASE_URL") or ""
    if not url.startswith("postgresql"):
        raise RuntimeError("PostgreSQL DATABASE_URL required for schema reset")

    # CI ephemeral service uses career_os with password testpass — allow that only.
    if "testpass@" in url and url.rstrip("/").endswith("/career_os"):
        return url

    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
    db_name = (parsed.path or "").lstrip("/").split("?")[0]
    if db_name in _ALLOWED_RESET_DB_NAMES:
        return url

    # Explicit opt-in for disposable DBs named like *_test
    if db_name.endswith("_test") or db_name.endswith("_e2e"):
        return url

    raise RuntimeError(
        f"Refusing to reset PostgreSQL database {db_name!r}. "
        "Owner database career_os must never be wiped by tests. "
        "Use career_os_e2e / career_os_test, or set DATABASE_URL to an isolated DB."
    )


def reset_public_schema(engine: Engine) -> None:
    """Drop and recreate public schema (avoids circular FK drop_all failures)."""
    url = str(engine.url)
    assert_safe_to_reset_database(url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
