"""Fail-closed recovery / owner-candidate database identity preflight."""

from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.services.database_identity import (
    CANDIDATE_DATABASE,
    PURPOSE_OWNER_CANDIDATE,
    PURPOSE_RECOVERY,
    RECOVERY_DATABASE,
    UUID_PATTERN,
    load_database_identity_record,
)

FORBIDDEN_DATABASES = {
    "career_os",
    "career_os_validation",
    "career_os_e2e",
    "career_os_test",
    "postgres",
}

PURPOSE_DATABASE = {
    PURPOSE_RECOVERY: RECOVERY_DATABASE,
    PURPOSE_OWNER_CANDIDATE: CANDIDATE_DATABASE,
}


class RecoveryIdentityPreflightError(RuntimeError):
    """Raised when recovery identity preflight fails."""


@dataclass(frozen=True)
class RecoveryIdentityPreflightResult:
    verified: bool
    purpose: str
    identity_uuid: str
    database: str
    identity_fingerprint: str
    verified_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def expected_recovery_purpose() -> str:
    purpose = (os.getenv("AAROHAN_DB_IDENTITY_PURPOSE") or "").strip().upper()
    if purpose not in {PURPOSE_RECOVERY, PURPOSE_OWNER_CANDIDATE}:
        raise RecoveryIdentityPreflightError(
            f"Recovery preflight requires RECOVERY or OWNER_CANDIDATE purpose, not {purpose!r}."
        )
    return purpose


def expected_recovery_uuid() -> str:
    uuid = (os.getenv("AAROHAN_DB_IDENTITY_UUID") or "").strip()
    if not uuid:
        raise RecoveryIdentityPreflightError("Missing AAROHAN_DB_IDENTITY_UUID for recovery preflight.")
    if not UUID_PATTERN.match(uuid):
        raise RecoveryIdentityPreflightError("AAROHAN_DB_IDENTITY_UUID must be a valid UUID v4.")
    return uuid


def identity_fingerprint(*, purpose: str, identity_uuid: str, database: str) -> str:
    payload = f"{purpose}|{identity_uuid.lower()}|{database}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_recovery_database_marker(
    engine: Engine,
    *,
    expected_purpose: str,
    expected_uuid: str,
    expected_database: str,
) -> None:
    with engine.connect() as conn:
        current_db = conn.execute(text("SELECT current_database()")).scalar()
        if str(current_db) != expected_database:
            raise RecoveryIdentityPreflightError(
                f"Connected database {current_db!r} does not match expected {expected_database!r}."
            )
        regclass = conn.execute(text("SELECT to_regclass('aarohan_meta.database_identity')")).scalar()
        if not regclass:
            raise RecoveryIdentityPreflightError("Missing aarohan_meta.database_identity marker table.")
        marker_count = conn.execute(text("SELECT count(*) FROM aarohan_meta.database_identity")).scalar()
        if marker_count != 1:
            raise RecoveryIdentityPreflightError(
                f"Expected exactly one aarohan_meta.database_identity row, found {marker_count}."
            )
    record = load_database_identity_record(engine)
    if record.purpose != expected_purpose:
        raise RecoveryIdentityPreflightError(
            f"Database marker purpose mismatch: expected={expected_purpose!r} marker={record.purpose!r}."
        )
    if record.identity_uuid.lower() != expected_uuid.lower():
        raise RecoveryIdentityPreflightError("Database marker UUID mismatch with environment.")


def validate_recovery_database_identity(
    *,
    database_url: str,
    database: str | None = None,
) -> RecoveryIdentityPreflightResult:
    expected_purpose = expected_recovery_purpose()
    expected_uuid = expected_recovery_uuid()
    expected_database = database or PURPOSE_DATABASE[expected_purpose]
    if expected_database in FORBIDDEN_DATABASES:
        raise RecoveryIdentityPreflightError(f"Forbidden recovery target database {expected_database!r}.")
    if expected_database != PURPOSE_DATABASE.get(expected_purpose):
        raise RecoveryIdentityPreflightError(
            f"Purpose {expected_purpose!r} cannot target database {expected_database!r}."
        )

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        validate_recovery_database_marker(
            engine,
            expected_purpose=expected_purpose,
            expected_uuid=expected_uuid,
            expected_database=expected_database,
        )
    finally:
        engine.dispose()

    fingerprint = identity_fingerprint(
        purpose=expected_purpose,
        identity_uuid=expected_uuid,
        database=expected_database,
    )
    return RecoveryIdentityPreflightResult(
        verified=True,
        purpose=expected_purpose,
        identity_uuid=expected_uuid,
        database=expected_database,
        identity_fingerprint=fingerprint,
        verified_at=_utc_now_iso(),
    )
