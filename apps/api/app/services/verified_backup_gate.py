"""Verified backup gate helpers for destructive-operation protection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BackupGateError(RuntimeError):
    """Raised when a verified backup cannot be produced."""


@dataclass(frozen=True)
class VerifiedBackupManifest:
    verified: bool
    database: str
    dump_path: str
    size_bytes: int
    sha256: str
    source_table_count: int
    restored_table_count: int
    critical_row_counts: dict[str, int]
    verified_at: str
    verification_database: str
    identity_purpose: str = ""
    identity_uuid: str = ""
    compose_project: str = ""
    postgres_service: str = ""
    postgres_container: str = ""
    identity_fingerprint: str = ""
    backup_started_at: str = ""
    backup_completed_at: str = ""
    verification_result: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_dump_header(path: Path) -> None:
    if not path.exists():
        raise BackupGateError(f"Backup file missing: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise BackupGateError("Backup file is empty")
    head = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:20]
    if not any("PostgreSQL database dump" in line for line in head):
        raise BackupGateError("Backup file does not contain PostgreSQL dump header")


def assert_checksum_matches(path: Path, expected_sha256: str) -> None:
    actual = sha256_file(path)
    if actual.lower() != expected_sha256.strip().lower():
        raise BackupGateError(
            f"Backup checksum mismatch: expected={expected_sha256.lower()} actual={actual}"
        )


def assert_restore_inventory_matches(
    *,
    source_tables: int,
    restored_tables: int,
    source_counts: dict[str, int],
    restored_counts: dict[str, int],
) -> None:
    if restored_tables != source_tables:
        raise BackupGateError(
            f"Restored table count mismatch: source={source_tables} restored={restored_tables}"
        )
    for key, source_value in source_counts.items():
        restored_value = restored_counts.get(key)
        if restored_value != source_value:
            raise BackupGateError(
                f"Row-count mismatch for {key}: source={source_value} restored={restored_value}"
            )


def load_manifest(path: Path) -> VerifiedBackupManifest:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return VerifiedBackupManifest(
        verified=bool(payload["verified"]),
        database=str(payload["database"]),
        dump_path=str(payload["dump_path"]),
        size_bytes=int(payload["size_bytes"]),
        sha256=str(payload["sha256"]),
        source_table_count=int(payload["source_table_count"]),
        restored_table_count=int(payload["restored_table_count"]),
        critical_row_counts={str(k): int(v) for k, v in payload["critical_row_counts"].items()},
        verified_at=str(payload["verified_at"]),
        verification_database=str(payload["verification_database"]),
        identity_purpose=str(payload.get("identity_purpose", "")),
        identity_uuid=str(payload.get("identity_uuid", "")),
        compose_project=str(payload.get("compose_project", "")),
        postgres_service=str(payload.get("postgres_service", "")),
        postgres_container=str(payload.get("postgres_container", "")),
        identity_fingerprint=str(payload.get("identity_fingerprint", "")),
        backup_started_at=str(payload.get("backup_started_at", "")),
        backup_completed_at=str(payload.get("backup_completed_at", "")),
        verification_result=str(payload.get("verification_result", "")),
    )


def assert_verified_manifest(manifest_path: Path, dump_path: Path | None = None) -> VerifiedBackupManifest:
    if not manifest_path.exists():
        raise BackupGateError(f"Backup manifest missing: {manifest_path}")
    manifest = load_manifest(manifest_path)
    if not manifest.verified:
        raise BackupGateError("Backup manifest is not verified")
    resolved_dump = Path(dump_path or manifest.dump_path)
    assert_dump_header(resolved_dump)
    assert_checksum_matches(resolved_dump, manifest.sha256)
    return manifest


def write_manifest(path: Path, manifest: VerifiedBackupManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.to_json(), encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
