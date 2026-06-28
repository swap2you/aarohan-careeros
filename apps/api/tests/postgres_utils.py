"""Shared helpers for PostgreSQL integration tests."""

from __future__ import annotations

from sqlalchemy import Engine, text


def reset_public_schema(engine: Engine) -> None:
    """Drop and recreate public schema (avoids circular FK drop_all failures)."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
