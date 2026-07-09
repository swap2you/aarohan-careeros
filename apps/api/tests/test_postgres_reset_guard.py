"""Guardrails: postgres schema reset must never wipe owner career_os."""

import pytest
from sqlalchemy.engine import make_url

from tests.postgres_utils import assert_safe_to_reset_database


def test_owner_career_os_url_is_rejected():
    with pytest.raises(RuntimeError, match="Refusing to reset"):
        assert_safe_to_reset_database(
            "postgresql+psycopg://career_os:secret@postgres:5432/career_os"
        )


def test_e2e_database_is_allowed():
    url = assert_safe_to_reset_database(
        "postgresql+psycopg://career_os:secret@postgres:5432/career_os_e2e"
    )
    assert url.endswith("career_os_e2e")


def test_ci_ephemeral_testpass_career_os_is_allowed():
    url = assert_safe_to_reset_database(
        "postgresql+psycopg://career_os:testpass@localhost:5432/career_os"
    )
    assert url.endswith("/career_os")


def test_redacted_engine_url_still_blocked_without_env():
    # SQLAlchemy often stringifies passwords as *** — must not allow wipe via that alone.
    with pytest.raises(RuntimeError, match="Refusing to reset"):
        assert_safe_to_reset_database(
            "postgresql+psycopg://career_os:***@localhost:5432/career_os"
        )


def test_named_test_database_is_allowed():
    url = assert_safe_to_reset_database(
        "postgresql+psycopg://career_os:secret@localhost:5432/career_os_test"
    )
    assert make_url(url.replace("postgresql+psycopg://", "postgresql://")).database == "career_os_test"
