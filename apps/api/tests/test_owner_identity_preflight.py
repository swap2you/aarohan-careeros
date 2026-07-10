"""Owner database identity preflight adversarial tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.services.owner_database_identity_preflight import (
    FORBIDDEN_DATABASES,
    OwnerIdentityPreflightError,
    OwnerIdentityPreflightResult,
    assert_owner_target_metadata,
    assert_same_run_backup_manifest,
    expected_owner_identity_purpose,
    expected_owner_identity_uuid,
    identity_fingerprint,
    sql_revalidate_owner_identity_marker,
    validate_owner_database_marker,
)
from app.services.verified_backup_gate import VerifiedBackupManifest, write_manifest


def _integration_database_name() -> str:
    url = os.environ.get("DATABASE_URL", "")
    return url.rsplit("/", 1)[-1].split("?", 1)[0]


def _integration_identity_purpose() -> str:
    return (os.environ.get("AAROHAN_DB_IDENTITY_PURPOSE") or "E2E").strip().upper()


def _owner_identity_result() -> OwnerIdentityPreflightResult:
    uuid = os.environ.get("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    return OwnerIdentityPreflightResult(
        verified=True,
        purpose="OWNER",
        identity_uuid=uuid,
        database="career_os",
        compose_project="aarohan-careeros",
        postgres_service="postgres",
        postgres_container="aarohan-careeros-postgres-1",
        host="127.0.0.1",
        port=5432,
        privileged_user="career_os",
        identity_fingerprint=identity_fingerprint(
            purpose="OWNER",
            identity_uuid=uuid,
            database="career_os",
            compose_project="aarohan-careeros",
            postgres_service="postgres",
        ),
        verified_at="2026-07-10T00:00:00+00:00",
    )


@pytest.mark.skipif(
    "postgresql" not in os.environ.get("DATABASE_URL", ""),
    reason="PostgreSQL integration URL required",
)
def test_marker_validation_on_isolated_postgres():
    expected_uuid = os.environ["AAROHAN_DB_IDENTITY_UUID"]
    purpose = _integration_identity_purpose()
    database = _integration_database_name()
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        validate_owner_database_marker(
            engine,
            expected_purpose=purpose,
            expected_uuid=expected_uuid,
            expected_database=database,
        )
    finally:
        engine.dispose()


def test_wrong_purpose_fails(monkeypatch):
    monkeypatch.delenv("AAROHAN_OWNER_DB_IDENTITY_UUID", raising=False)
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "E2E")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    with pytest.raises(OwnerIdentityPreflightError, match="OWNER"):
        expected_owner_identity_purpose()


@pytest.mark.skipif(
    "postgresql" not in os.environ.get("DATABASE_URL", ""),
    reason="PostgreSQL integration URL required",
)
def test_wrong_uuid_fails():
    purpose = _integration_identity_purpose()
    database = _integration_database_name()
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with pytest.raises(OwnerIdentityPreflightError, match="UUID mismatch"):
            validate_owner_database_marker(
                engine,
                expected_purpose=purpose,
                expected_uuid="22222222-2222-4222-8222-222222222222",
                expected_database=database,
            )
    finally:
        engine.dispose()


def test_validation_database_fails():
    with pytest.raises(OwnerIdentityPreflightError, match="career_os"):
        assert_owner_target_metadata(
            database="career_os_validation",
            compose_project="aarohan-careeros",
            postgres_service="postgres",
            postgres_container="aarohan-careeros-postgres-1",
            host="127.0.0.1",
            port=5432,
        )


def test_e2e_database_fails():
    with pytest.raises(OwnerIdentityPreflightError, match="career_os"):
        assert_owner_target_metadata(
            database="career_os_e2e",
            compose_project="aarohan-careeros-test",
            postgres_service="postgres-e2e",
            postgres_container="aarohan-careeros-test-postgres-e2e-1",
            host="127.0.0.1",
            port=5433,
        )


def test_recovery_database_forbidden():
    assert "career_os_recovery" in FORBIDDEN_DATABASES


def test_wrong_compose_project_fails():
    with pytest.raises(OwnerIdentityPreflightError, match="compose project"):
        assert_owner_target_metadata(
            database="career_os",
            compose_project="aarohan-careeros-test",
            postgres_service="postgres",
            postgres_container="aarohan-careeros-test-postgres-e2e-1",
            host="127.0.0.1",
            port=5432,
        )


def test_wrong_postgres_service_fails():
    with pytest.raises(OwnerIdentityPreflightError, match="postgres service"):
        assert_owner_target_metadata(
            database="career_os",
            compose_project="aarohan-careeros",
            postgres_service="postgres-e2e",
            postgres_container="aarohan-careeros-postgres-1",
            host="127.0.0.1",
            port=5432,
        )


def test_backup_manifest_binds_identity(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "OWNER")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    identity = _owner_identity_result()
    dump = tmp_path / "career_os.sql"
    dump.write_text("--\n-- PostgreSQL database dump\n--\n", encoding="utf-8")
    manifest_path = tmp_path / "BACKUP-MANIFEST.json"
    manifest = VerifiedBackupManifest(
        verified=True,
        database="career_os",
        dump_path=str(dump),
        size_bytes=dump.stat().st_size,
        sha256="deadbeef",
        source_table_count=1,
        restored_table_count=1,
        critical_row_counts={"jobs": 1},
        verified_at="2026-07-10T00:00:00+00:00",
        verification_database="backup_verify",
        identity_purpose=identity.purpose,
        identity_uuid=identity.identity_uuid,
        compose_project=identity.compose_project,
        postgres_service=identity.postgres_service,
        postgres_container=identity.postgres_container,
        identity_fingerprint=identity.identity_fingerprint,
        backup_started_at="2026-07-10T00:00:00+00:00",
        backup_completed_at="2026-07-10T00:00:01+00:00",
        verification_result="restore_verified",
    )
    write_manifest(manifest_path, manifest)
    with pytest.raises(Exception):
        assert_same_run_backup_manifest(manifest_path, identity=identity, dump_path=dump)


def test_backup_manifest_wrong_uuid_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "OWNER")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    identity = _owner_identity_result()
    manifest_path = tmp_path / "BACKUP-MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "verified": True,
                "database": "career_os",
                "identity_purpose": "OWNER",
                "identity_uuid": "22222222-2222-4222-8222-222222222222",
                "compose_project": identity.compose_project,
                "postgres_service": identity.postgres_service,
                "identity_fingerprint": identity.identity_fingerprint,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OwnerIdentityPreflightError, match="UUID"):
        assert_same_run_backup_manifest(manifest_path, identity=identity)


def test_backup_manifest_wrong_database_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "OWNER")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    identity = _owner_identity_result()
    manifest_path = tmp_path / "BACKUP-MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "verified": True,
                "database": "career_os_validation",
                "identity_purpose": "OWNER",
                "identity_uuid": identity.identity_uuid,
                "compose_project": identity.compose_project,
                "postgres_service": identity.postgres_service,
                "identity_fingerprint": identity.identity_fingerprint,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OwnerIdentityPreflightError, match="database"):
        assert_same_run_backup_manifest(manifest_path, identity=identity)


def test_stale_backup_manifest_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_PURPOSE", "OWNER")
    monkeypatch.setenv("AAROHAN_DB_IDENTITY_UUID", "11111111-1111-4111-8111-111111111111")
    identity = _owner_identity_result()
    manifest_path = tmp_path / "BACKUP-MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "verified": True,
                "database": "career_os",
                "identity_purpose": "OWNER",
                "identity_uuid": identity.identity_uuid,
                "compose_project": identity.compose_project,
                "postgres_service": identity.postgres_service,
                "identity_fingerprint": identity.identity_fingerprint,
                "backup_started_at": "2020-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OwnerIdentityPreflightError, match="stale"):
        assert_same_run_backup_manifest(
            manifest_path,
            identity=identity,
            same_run_started_at="2026-07-10T00:00:00+00:00",
        )


def test_sql_revalidate_contains_uuid():
    sql = sql_revalidate_owner_identity_marker("11111111-1111-4111-8111-111111111111")
    assert "11111111-1111-4111-8111-111111111111" in sql
    assert "OWNER" in sql


def test_privileged_helper_scan_detects_fixture():
    root = Path(__file__).resolve().parents[3]
    fixture = root / "validation" / "fixtures" / "unguarded_privileged_helper_fixture.ps1"
    text = fixture.read_text(encoding="utf-8")
    assert "pg_dump" in text
    assert "Assert-AarohanOwnerDatabaseIdentity" not in text


def test_missing_uuid_env_fails(monkeypatch):
    monkeypatch.delenv("AAROHAN_DB_IDENTITY_UUID", raising=False)
    monkeypatch.delenv("AAROHAN_OWNER_DB_IDENTITY_UUID", raising=False)
    with pytest.raises(OwnerIdentityPreflightError, match="Missing owner identity UUID"):
        expected_owner_identity_uuid()
