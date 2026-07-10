"""Database identity markers, role guards, and startup validation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from app.config import settings

PURPOSE_OWNER = "OWNER"
PURPOSE_E2E = "E2E"
PURPOSE_CI = "CI"
PURPOSE_RECOVERY = "RECOVERY"
PURPOSE_OWNER_CANDIDATE = "OWNER_CANDIDATE"

TEST_PURPOSES = {PURPOSE_E2E, PURPOSE_CI}
RECOVERY_PURPOSES = {PURPOSE_RECOVERY, PURPOSE_OWNER_CANDIDATE}
ALL_PURPOSES = {PURPOSE_OWNER, PURPOSE_E2E, PURPOSE_CI, PURPOSE_RECOVERY, PURPOSE_OWNER_CANDIDATE}

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)

OWNER_RUNTIME_USER = "career_os_runtime"
OWNER_MIGRATE_USER = "career_os_migrate"
E2E_RUNTIME_USER = "career_os_e2e_runtime"
E2E_MIGRATE_USER = "career_os_e2e_migrate"
E2E_BOOTSTRAP_USER = "career_os_e2e"
RECOVERY_RUNTIME_USER = "career_os_recovery_runtime"
RECOVERY_MIGRATE_USER = "career_os_recovery_migrate"
CANDIDATE_RUNTIME_USER = "career_os_candidate_runtime"
CANDIDATE_MIGRATE_USER = "career_os_candidate_migrate"
MIGRATE_USERS = {OWNER_MIGRATE_USER, E2E_MIGRATE_USER, RECOVERY_MIGRATE_USER, CANDIDATE_MIGRATE_USER}

RECOVERY_DATABASE = "career_os_recovery"
CANDIDATE_DATABASE = "career_os_owner_candidate"


@dataclass(frozen=True)
class DatabaseIdentityRecord:
    purpose: str
    identity_uuid: str
    schema_version: str | None
    created_at: Any


def runtime_profile() -> str:
    env = os.getenv("AAROHAN_RUNTIME_PROFILE")
    if env:
        return env.strip().lower()
    return (settings.aarohan_runtime_profile or "default").strip().lower()


def identity_purpose() -> str:
    env = os.getenv("AAROHAN_DB_IDENTITY_PURPOSE")
    if env:
        return env.strip().upper()
    return (settings.aarohan_db_identity_purpose or "").strip().upper()


def identity_uuid() -> str:
    env = os.getenv("AAROHAN_DB_IDENTITY_UUID")
    if env:
        return env.strip()
    return (settings.aarohan_db_identity_uuid or "").strip()


def migration_database_url() -> str:
    return (
        os.getenv("MIGRATION_DATABASE_URL")
        or settings.migration_database_url
        or settings.database_url
    )


def is_postgresql_url(database_url: str) -> bool:
    return database_url.startswith("postgresql")


def should_enforce_identity(database_url: str | None = None) -> bool:
    url = database_url or settings.database_url or ""
    return is_postgresql_url(url)


def assert_identity_configured() -> None:
    purpose = identity_purpose()
    uuid = identity_uuid()
    if purpose not in ALL_PURPOSES:
        raise RuntimeError(
            f"Invalid or missing AAROHAN_DB_IDENTITY_PURPOSE ({purpose!r}). "
            f"Expected one of: {', '.join(sorted(ALL_PURPOSES))}."
        )
    if not UUID_PATTERN.match(uuid):
        raise RuntimeError("Invalid or missing AAROHAN_DB_IDENTITY_UUID (UUID v4 required).")


def assert_test_infrastructure(action: str) -> None:
    assert_identity_configured()
    if identity_purpose() not in TEST_PURPOSES:
        raise RuntimeError(
            f"Refusing {action}: AAROHAN_DB_IDENTITY_PURPOSE must be E2E or CI, "
            f"not {identity_purpose()!r}."
        )


def assert_owner_runtime_not_testing(action: str = "pytest") -> None:
    if runtime_profile() == "owner":
        raise RuntimeError(
            f"Refusing {action} on owner runtime image (AAROHAN_RUNTIME_PROFILE=owner)."
        )
    if identity_purpose() == PURPOSE_OWNER and action == "pytest":
        raise RuntimeError(f"Refusing {action} when database identity purpose is OWNER.")


def _url_parts(database_url: str) -> tuple[str, str, str, str]:
    try:
        u = make_url(database_url)
        return u.database or "", u.username or "", u.password or "", u.host or ""
    except Exception:
        parsed = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://", 1))
        db_name = (parsed.path or "").lstrip("/").split("?")[0]
        return db_name, parsed.username or "", parsed.password or "", parsed.hostname or ""


def expected_runtime_user_for_purpose(purpose: str) -> str:
    if purpose in {PURPOSE_OWNER, PURPOSE_CI}:
        return OWNER_RUNTIME_USER
    if purpose == PURPOSE_E2E:
        return E2E_RUNTIME_USER
    if purpose == PURPOSE_RECOVERY:
        return RECOVERY_RUNTIME_USER
    if purpose == PURPOSE_OWNER_CANDIDATE:
        return CANDIDATE_RUNTIME_USER
    raise RuntimeError(f"Unsupported identity purpose {purpose!r}")


def assert_connection_matches_identity(database_url: str) -> None:
    """Reject spoofed URLs that do not match declared DB identity."""
    if not should_enforce_identity(database_url):
        return

    assert_identity_configured()
    purpose = identity_purpose()
    db_name, username, _password, host = _url_parts(database_url)
    expected_user = expected_runtime_user_for_purpose(purpose)

    if (
        purpose == PURPOSE_E2E
        and db_name in {"career_os_e2e", "career_os_test"}
        and username in {E2E_MIGRATE_USER, E2E_BOOTSTRAP_USER}
    ):
        return

    if (
        purpose == PURPOSE_OWNER_CANDIDATE
        and db_name == CANDIDATE_DATABASE
        and username in {CANDIDATE_MIGRATE_USER, "career_os"}
    ):
        return

    if (
        purpose == PURPOSE_RECOVERY
        and db_name == RECOVERY_DATABASE
        and username in {RECOVERY_MIGRATE_USER, "career_os"}
    ):
        return

    if username in MIGRATE_USERS:
        if purpose == PURPOSE_OWNER and db_name == "career_os" and username == OWNER_MIGRATE_USER:
            return
        if purpose == PURPOSE_CI and db_name == "career_os" and username == OWNER_MIGRATE_USER:
            return
        if purpose == PURPOSE_E2E and db_name in {"career_os_e2e", "career_os_test"} and username == E2E_MIGRATE_USER:
            return
        if purpose == PURPOSE_RECOVERY and db_name == RECOVERY_DATABASE and username == RECOVERY_MIGRATE_USER:
            return
        if (
            purpose == PURPOSE_OWNER_CANDIDATE
            and db_name == CANDIDATE_DATABASE
            and username == CANDIDATE_MIGRATE_USER
        ):
            return
        raise RuntimeError(
            f"Migration role {username!r} cannot be used for identity purpose {purpose!r}."
        )

    if purpose == PURPOSE_OWNER:
        if db_name != "career_os":
            raise RuntimeError(f"Owner identity cannot target database {db_name!r}.")
        if username != expected_user:
            raise RuntimeError(
                f"Owner runtime must use {expected_user}, not {username!r}."
            )
        if host in {"postgres-e2e", "127.0.0.1"} and "5433" in database_url:
            raise RuntimeError("Owner identity cannot target isolated test postgres.")
        return

    if purpose == PURPOSE_CI:
        if db_name != "career_os":
            raise RuntimeError(f"CI identity cannot target database {db_name!r}.")
        if username != expected_user:
            raise RuntimeError(
                f"CI runtime must use {expected_user}, not {username!r}."
            )
        return

    if purpose == PURPOSE_E2E:
        if db_name not in {"career_os_e2e", "career_os_test"}:
            raise RuntimeError(
                f"E2E identity cannot target database {db_name!r}."
            )
        if username != expected_user:
            raise RuntimeError(
                f"E2E identity must use {expected_user}, not {username!r}."
            )
        if host == "postgres" and purpose == PURPOSE_E2E:
            raise RuntimeError(
                "E2E identity cannot use owner postgres host 'postgres'; use postgres-e2e."
            )
        return

    if purpose == PURPOSE_RECOVERY:
        if db_name != RECOVERY_DATABASE:
            raise RuntimeError(f"Recovery identity cannot target database {db_name!r}.")
        if username != RECOVERY_RUNTIME_USER:
            raise RuntimeError(
                f"Recovery runtime must use {RECOVERY_RUNTIME_USER}, not {username!r}."
            )
        return

    if purpose == PURPOSE_OWNER_CANDIDATE:
        if db_name != CANDIDATE_DATABASE:
            raise RuntimeError(f"Owner candidate identity cannot target database {db_name!r}.")
        if username != CANDIDATE_RUNTIME_USER:
            raise RuntimeError(
                f"Owner candidate runtime must use {CANDIDATE_RUNTIME_USER}, not {username!r}."
            )
        return


def load_database_identity_record(engine: Engine) -> DatabaseIdentityRecord:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT purpose, identity_uuid, schema_version, created_at
                FROM aarohan_meta.database_identity
                ORDER BY id
                """
            )
        ).fetchall()
    if len(rows) != 1:
        raise RuntimeError(
            f"Expected exactly one aarohan_meta.database_identity row, found {len(rows)}."
        )
    row = rows[0]
    return DatabaseIdentityRecord(
        purpose=str(row.purpose).upper(),
        identity_uuid=str(row.identity_uuid),
        schema_version=row.schema_version,
        created_at=row.created_at,
    )


def validate_database_identity_marker(engine: Engine, database_url: str | None = None) -> DatabaseIdentityRecord:
    if not should_enforce_identity(database_url):
        return DatabaseIdentityRecord("", "", None, None)

    assert_identity_configured()
    record = load_database_identity_record(engine)
    expected_purpose = identity_purpose()
    expected_uuid = identity_uuid()

    if record.purpose != expected_purpose:
        raise RuntimeError(
            f"Database identity purpose mismatch: env={expected_purpose!r} "
            f"marker={record.purpose!r}."
        )
    if record.identity_uuid.lower() != expected_uuid.lower():
        raise RuntimeError(
            "Database identity UUID mismatch between environment and immutable marker."
        )
    return record


def validate_runtime_database(database_url: str | None = None) -> None:
    """Fail-closed validation for runtime connections."""
    url = database_url or settings.database_url
    if not url:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL runtime validation.")
    if not should_enforce_identity(url):
        return

    assert_connection_matches_identity(url)
    from sqlalchemy import create_engine

    engine = create_engine(url, pool_pre_ping=True)
    try:
        validate_database_identity_marker(engine, url)
    finally:
        engine.dispose()


def identity_marker_table_exists(engine: Engine) -> bool:
    with engine.connect() as conn:
        regclass = conn.execute(
            text("SELECT to_regclass('aarohan_meta.database_identity')")
        ).scalar()
    return regclass is not None


def validate_before_migration(database_url: str | None = None) -> None:
    url = database_url or migration_database_url()
    if not should_enforce_identity(url):
        return
    from sqlalchemy import create_engine

    engine = create_engine(url, pool_pre_ping=True)
    try:
        if not identity_marker_table_exists(engine):
            return
        with engine.connect() as conn:
            marker_count = conn.execute(
                text("SELECT count(*) FROM aarohan_meta.database_identity")
            ).scalar()
        if not marker_count:
            return
    finally:
        engine.dispose()

    assert_identity_configured()
    engine = create_engine(url, pool_pre_ping=True)
    try:
        runtime_url = settings.database_url
        if runtime_url:
            assert_connection_matches_identity(runtime_url)
        validate_database_identity_marker(engine, runtime_url)
    finally:
        engine.dispose()


def assert_destructive_token(expected_action: str, provided_token: str | None = None) -> None:
    expected = (
        settings.destructive_operation_token or os.getenv("AAROHAN_DESTRUCTIVE_TOKEN") or ""
    ).strip()
    token = (provided_token or "").strip()
    if not expected:
        raise RuntimeError(
            f"Refusing {expected_action}: AAROHAN_DESTRUCTIVE_TOKEN is not configured."
        )
    if token != expected:
        raise RuntimeError(f"Refusing {expected_action}: destructive token mismatch.")


def identity_payload() -> dict[str, str]:
    return {
        "purpose": identity_purpose() or "unknown",
        "uuid": identity_uuid() or "unknown",
        "runtime_profile": runtime_profile(),
    }
