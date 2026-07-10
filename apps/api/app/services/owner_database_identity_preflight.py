"""Fail-closed owner database identity preflight for privileged helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.services.database_identity import (
    PURPOSE_OWNER,
    UUID_PATTERN,
    load_database_identity_record,
)

OWNER_COMPOSE_PROJECT = "aarohan-careeros"
OWNER_POSTGRES_SERVICE = "postgres"
OWNER_DATABASE = "career_os"
OWNER_HOST = "127.0.0.1"
OWNER_PORT = 5432

FORBIDDEN_DATABASES = {
    "career_os_validation",
    "career_os_e2e",
    "career_os_test",
    "career_os_recovery",
    "career_os_owner_candidate",
    "postgres",
}

FORBIDDEN_COMPOSE_PROJECTS = {
    "aarohan-careeros-test",
}

UUID_ENV_KEYS = ("AAROHAN_OWNER_DB_IDENTITY_UUID", "AAROHAN_DB_IDENTITY_UUID")
PURPOSE_ENV_KEYS = ("AAROHAN_DB_IDENTITY_PURPOSE",)


class OwnerIdentityPreflightError(RuntimeError):
    """Raised when owner identity preflight fails."""


@dataclass(frozen=True)
class OwnerIdentityPreflightResult:
    verified: bool
    purpose: str
    identity_uuid: str
    database: str
    compose_project: str
    postgres_service: str
    postgres_container: str
    host: str
    port: int
    privileged_user: str
    identity_fingerprint: str
    verified_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def expected_owner_identity_uuid() -> str:
    for key in UUID_ENV_KEYS:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    raise OwnerIdentityPreflightError(
        "Missing owner identity UUID (AAROHAN_OWNER_DB_IDENTITY_UUID or AAROHAN_DB_IDENTITY_UUID)."
    )


def expected_owner_identity_purpose() -> str:
    if (os.getenv("AAROHAN_OWNER_DB_IDENTITY_UUID") or "").strip():
        return PURPOSE_OWNER
    for key in PURPOSE_ENV_KEYS:
        value = (os.getenv(key) or "").strip().upper()
        if value:
            if value != PURPOSE_OWNER:
                raise OwnerIdentityPreflightError(
                    f"Owner privileged helper requires AAROHAN_DB_IDENTITY_PURPOSE=OWNER, not {value!r}."
                )
            return value
    raise OwnerIdentityPreflightError("Missing AAROHAN_DB_IDENTITY_PURPOSE=OWNER.")


def identity_fingerprint(
    *,
    purpose: str,
    identity_uuid: str,
    database: str,
    compose_project: str,
    postgres_service: str,
) -> str:
    payload = f"{purpose}|{identity_uuid.lower()}|{database}|{compose_project}|{postgres_service}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_owner_target_metadata(
    *,
    database: str,
    compose_project: str,
    postgres_service: str,
    postgres_container: str,
    host: str,
    port: int,
) -> None:
    if database != OWNER_DATABASE:
        raise OwnerIdentityPreflightError(
            f"Owner privileged helper cannot target database {database!r}; expected {OWNER_DATABASE!r}."
        )
    if database in FORBIDDEN_DATABASES:
        raise OwnerIdentityPreflightError(f"Forbidden owner helper target database {database!r}.")
    if compose_project in FORBIDDEN_COMPOSE_PROJECTS:
        raise OwnerIdentityPreflightError(
            f"Owner privileged helper cannot use compose project {compose_project!r}."
        )
    if compose_project != OWNER_COMPOSE_PROJECT:
        raise OwnerIdentityPreflightError(
            f"Owner privileged helper must use compose project {OWNER_COMPOSE_PROJECT!r}, not {compose_project!r}."
        )
    if postgres_service != OWNER_POSTGRES_SERVICE:
        raise OwnerIdentityPreflightError(
            f"Owner privileged helper must use postgres service {OWNER_POSTGRES_SERVICE!r}, not {postgres_service!r}."
        )
    if "test" in postgres_container.lower() and "careeros-test" in postgres_container.lower():
        raise OwnerIdentityPreflightError(
            f"Owner privileged helper cannot use test postgres container {postgres_container!r}."
        )
    if port == 5433:
        raise OwnerIdentityPreflightError("Owner privileged helper cannot target isolated test postgres port 5433.")
    if host not in {OWNER_HOST, "localhost", "postgres"}:
        raise OwnerIdentityPreflightError(f"Owner privileged helper host {host!r} is not the owner postgres service.")


def validate_owner_database_marker(
    engine: Engine,
    *,
    expected_purpose: str,
    expected_uuid: str,
    expected_database: str = OWNER_DATABASE,
) -> None:
    with engine.connect() as conn:
        current_db = conn.execute(text("SELECT current_database()")).scalar()
        if str(current_db) != expected_database:
            raise OwnerIdentityPreflightError(
                f"Connected database {current_db!r} does not match expected {expected_database!r}."
            )
        regclass = conn.execute(text("SELECT to_regclass('aarohan_meta.database_identity')")).scalar()
        if not regclass:
            raise OwnerIdentityPreflightError("Missing aarohan_meta.database_identity marker table.")
        marker_count = conn.execute(text("SELECT count(*) FROM aarohan_meta.database_identity")).scalar()
        if marker_count != 1:
            raise OwnerIdentityPreflightError(
                f"Expected exactly one aarohan_meta.database_identity row, found {marker_count}."
            )
    record = load_database_identity_record(engine)
    if record.purpose != expected_purpose:
        raise OwnerIdentityPreflightError(
            f"Database marker purpose mismatch: expected={expected_purpose!r} marker={record.purpose!r}."
        )
    if record.identity_uuid.lower() != expected_uuid.lower():
        raise OwnerIdentityPreflightError("Database marker UUID mismatch with environment.")


def validate_owner_database_identity(
    *,
    database_url: str,
    database: str = OWNER_DATABASE,
    compose_project: str = OWNER_COMPOSE_PROJECT,
    postgres_service: str = OWNER_POSTGRES_SERVICE,
    postgres_container: str = "",
    host: str = OWNER_HOST,
    port: int = OWNER_PORT,
    privileged_user: str = "career_os",
) -> OwnerIdentityPreflightResult:
    expected_purpose = expected_owner_identity_purpose()
    expected_uuid = expected_owner_identity_uuid()
    if not UUID_PATTERN.match(expected_uuid):
        raise OwnerIdentityPreflightError("AAROHAN_DB_IDENTITY_UUID must be a valid UUID v4.")

    assert_owner_target_metadata(
        database=database,
        compose_project=compose_project,
        postgres_service=postgres_service,
        postgres_container=postgres_container or f"{compose_project}-{postgres_service}-1",
        host=host,
        port=port,
    )

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        validate_owner_database_marker(
            engine,
            expected_purpose=expected_purpose,
            expected_uuid=expected_uuid,
            expected_database=database,
        )
    finally:
        engine.dispose()

    fingerprint = identity_fingerprint(
        purpose=expected_purpose,
        identity_uuid=expected_uuid,
        database=database,
        compose_project=compose_project,
        postgres_service=postgres_service,
    )
    return OwnerIdentityPreflightResult(
        verified=True,
        purpose=expected_purpose,
        identity_uuid=expected_uuid,
        database=database,
        compose_project=compose_project,
        postgres_service=postgres_service,
        postgres_container=postgres_container or f"{compose_project}-{postgres_service}-1",
        host=host,
        port=port,
        privileged_user=privileged_user,
        identity_fingerprint=fingerprint,
        verified_at=_utc_now_iso(),
    )


def assert_same_run_backup_manifest(
    manifest_path: str | os.PathLike[str],
    *,
    identity: OwnerIdentityPreflightResult,
    dump_path: str | os.PathLike[str] | None = None,
    same_run_started_at: str | None = None,
) -> dict[str, Any]:
    path = os.fspath(manifest_path)
    if not os.path.exists(path):
        raise OwnerIdentityPreflightError(f"Backup manifest missing: {path}")
    payload: dict[str, Any] = json.loads(open(path, encoding="utf-8").read())
    if not payload.get("verified"):
        raise OwnerIdentityPreflightError("Backup manifest is not verified.")
    if payload.get("database") != identity.database:
        raise OwnerIdentityPreflightError("Backup manifest database does not match owner identity target.")
    if payload.get("identity_purpose") != identity.purpose:
        raise OwnerIdentityPreflightError("Backup manifest purpose does not match owner identity.")
    if str(payload.get("identity_uuid", "")).lower() != identity.identity_uuid.lower():
        raise OwnerIdentityPreflightError("Backup manifest UUID does not match owner identity.")
    if payload.get("compose_project") != identity.compose_project:
        raise OwnerIdentityPreflightError("Backup manifest compose project mismatch.")
    if payload.get("postgres_service") != identity.postgres_service:
        raise OwnerIdentityPreflightError("Backup manifest postgres service mismatch.")
    if payload.get("identity_fingerprint") != identity.identity_fingerprint:
        raise OwnerIdentityPreflightError("Backup manifest identity fingerprint mismatch.")
    if same_run_started_at:
        backup_started = payload.get("backup_started_at") or payload.get("verified_at")
        if not backup_started or backup_started < same_run_started_at:
            raise OwnerIdentityPreflightError("Backup manifest is stale relative to current execution.")
    if dump_path is not None:
        from app.services.verified_backup_gate import assert_verified_manifest

        assert_verified_manifest(path, dump_path)
    return payload


def sql_revalidate_owner_identity_marker(expected_uuid: str, expected_purpose: str = PURPOSE_OWNER) -> str:
    safe_uuid = expected_uuid.replace("'", "''")
    safe_purpose = expected_purpose.replace("'", "''")
    return f"""
DO $$
DECLARE
  marker_count integer;
  marker_purpose text;
  marker_uuid text;
BEGIN
  SELECT count(*) INTO marker_count FROM aarohan_meta.database_identity;
  IF marker_count <> 1 THEN
    RAISE EXCEPTION 'owner identity marker count %', marker_count;
  END IF;
  SELECT purpose, identity_uuid INTO marker_purpose, marker_uuid
  FROM aarohan_meta.database_identity
  ORDER BY id
  LIMIT 1;
  IF upper(marker_purpose) <> upper('{safe_purpose}') THEN
    RAISE EXCEPTION 'owner identity purpose mismatch';
  END IF;
  IF lower(marker_uuid) <> lower('{safe_uuid}') THEN
    RAISE EXCEPTION 'owner identity uuid mismatch';
  END IF;
  IF current_database() <> '{OWNER_DATABASE}' THEN
    RAISE EXCEPTION 'owner identity database mismatch';
  END IF;
END $$;
"""
