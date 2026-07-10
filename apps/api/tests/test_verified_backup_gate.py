"""Verified backup gate unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.verified_backup_gate import (
    BackupGateError,
    VerifiedBackupManifest,
    assert_checksum_matches,
    assert_dump_header,
    assert_restore_inventory_matches,
    assert_verified_manifest,
    sha256_file,
    utc_now_iso,
    write_manifest,
)


def test_dump_header_rejects_empty_file(tmp_path: Path):
    dump = tmp_path / "empty.sql"
    dump.write_text("", encoding="utf-8")
    with pytest.raises(BackupGateError, match="empty"):
        assert_dump_header(dump)


def test_dump_header_requires_postgres_banner(tmp_path: Path):
    dump = tmp_path / "bad.sql"
    dump.write_text("not a dump", encoding="utf-8")
    with pytest.raises(BackupGateError, match="PostgreSQL dump header"):
        assert_dump_header(dump)


def test_checksum_mismatch_blocks_operation(tmp_path: Path):
    dump = tmp_path / "career_os.sql"
    dump.write_text(
        "--\n-- PostgreSQL database dump\n--\nCREATE TABLE jobs(id int);\n",
        encoding="utf-8",
    )
    with pytest.raises(BackupGateError, match="checksum mismatch"):
        assert_checksum_matches(dump, "0" * 64)


def test_restore_inventory_mismatch_blocks_operation():
    with pytest.raises(BackupGateError, match="table count mismatch"):
        assert_restore_inventory_matches(
            source_tables=10,
            restored_tables=9,
            source_counts={"jobs": 1},
            restored_counts={"jobs": 1},
        )


def test_row_count_mismatch_blocks_operation():
    with pytest.raises(BackupGateError, match="Row-count mismatch"):
        assert_restore_inventory_matches(
            source_tables=1,
            restored_tables=1,
            source_counts={"jobs": 5},
            restored_counts={"jobs": 4},
        )


def test_successful_manifest_permits_gated_step(tmp_path: Path):
    dump = tmp_path / "career_os.sql"
    dump.write_text(
        "--\n-- PostgreSQL database dump\n--\nCREATE TABLE jobs(id int);\n",
        encoding="utf-8",
    )
    digest = sha256_file(dump)
    manifest_path = tmp_path / "BACKUP-MANIFEST.json"
    manifest = VerifiedBackupManifest(
        verified=True,
        database="career_os",
        dump_path=str(dump),
        size_bytes=dump.stat().st_size,
        sha256=digest,
        source_table_count=1,
        restored_table_count=1,
        critical_row_counts={"jobs": 1},
        verified_at=utc_now_iso(),
        verification_database="backup_verify_career_os",
    )
    write_manifest(manifest_path, manifest)
    loaded = assert_verified_manifest(manifest_path, dump)
    assert loaded.verified is True
    assert loaded.sha256 == digest


def test_corrupted_manifest_blocks_operation(tmp_path: Path):
    dump = tmp_path / "career_os.sql"
    dump.write_text("--\n-- PostgreSQL database dump\n--\n", encoding="utf-8")
    manifest_path = tmp_path / "BACKUP-MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "verified": True,
                "database": "career_os",
                "dump_path": str(dump),
                "size_bytes": dump.stat().st_size,
                "sha256": "deadbeef",
                "source_table_count": 1,
                "restored_table_count": 1,
                "critical_row_counts": {"jobs": 0},
                "verified_at": utc_now_iso(),
                "verification_database": "backup_verify",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(BackupGateError, match="checksum mismatch"):
        assert_verified_manifest(manifest_path, dump)
