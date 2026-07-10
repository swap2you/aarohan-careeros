#!/usr/bin/env python3
"""Verified candidate backup and restore verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

CRITICAL_TABLES = [
    "users",
    "jobs",
    "applications",
    "oauth_tokens",
    "processed_gmail_messages",
    "recruiter_signals",
    "audit_logs",
    "companies",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _psql(container: str, user: str, db: str, sql: str) -> tuple[int, str]:
    proc = _run(["docker", "exec", container, "psql", "-U", user, "-d", db, "-Atc", sql])
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _table_inventory(container: str, user: str, db: str) -> list[str]:
    code, out = _psql(
        container,
        user,
        db,
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;",
    )
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _row_counts(container: str, user: str, db: str, tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables:
        code, out = _psql(container, user, db, f"SELECT count(*) FROM {table};")
        counts[table] = int(out.strip()) if code == 0 and out.strip().isdigit() else -1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Candidate backup and restore verification")
    parser.add_argument("--container", default="aarohan-careeros-postgres-1")
    parser.add_argument("--pg-user", default="career_os")
    parser.add_argument("--source-db", default="career_os_owner_candidate")
    parser.add_argument("--dumps-dir", required=True)
    parser.add_argument("--manifest-json", required=True)
    parser.add_argument("--verification-json", required=True)
    parser.add_argument("--identity-uuid", required=True)
    args = parser.parse_args(argv)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dumps_dir = Path(args.dumps_dir)
    dumps_dir.mkdir(parents=True, exist_ok=True)
    dump_path = dumps_dir / f"career_os_owner_candidate_final_{ts}.sql"
    container_dump = f"/tmp/candidate_final_{ts}.sql"

    dump_proc = _run([
        "docker", "exec", args.container,
        "pg_dump", "-U", args.pg_user, "-d", args.source_db,
        "-Fp", "--no-owner", "--no-acl", "-f", container_dump,
    ])
    if dump_proc.returncode != 0:
        print(dump_proc.stderr, file=sys.stderr)
        return 1
    cp_proc = _run(["docker", "cp", f"{args.container}:{container_dump}", str(dump_path)])
    _run(["docker", "exec", args.container, "rm", "-f", container_dump])
    if cp_proc.returncode != 0 or not dump_path.is_file() or dump_path.stat().st_size <= 0:
        return 1

    sha = _sha256(dump_path)
    verify_db = f"recovery_verify_final_{ts}"[:63]
    _psql(args.container, args.pg_user, "postgres", f'DROP DATABASE IF EXISTS "{verify_db}";')
    code, out = _psql(args.container, args.pg_user, "postgres", f'CREATE DATABASE "{verify_db}" OWNER {args.pg_user};')
    if code != 0:
        return 1

    cp_in = _run(["docker", "cp", str(dump_path), f"{args.container}:{container_dump}"])
    restore_proc = _run([
        "docker", "exec", args.container,
        "psql", "-U", args.pg_user, "-d", verify_db, "-v", "ON_ERROR_STOP=1", "-f", container_dump,
    ])
    _run(["docker", "exec", args.container, "rm", "-f", container_dump])

    source_tables = _table_inventory(args.container, args.pg_user, args.source_db)
    restored_tables = _table_inventory(args.container, args.pg_user, verify_db)
    source_counts = _row_counts(args.container, args.pg_user, args.source_db, source_tables)
    restored_counts = _row_counts(args.container, args.pg_user, verify_db, restored_tables)
    mismatches = []
    for table in source_tables:
        if source_counts.get(table) != restored_counts.get(table):
            mismatches.append({
                "table": table,
                "source": source_counts.get(table),
                "restored": restored_counts.get(table),
            })

    marker_code, marker_out = _psql(
        args.container,
        args.pg_user,
        verify_db,
        "SELECT purpose||'|'||identity_uuid FROM aarohan_meta.database_identity LIMIT 1;",
    )
    oauth_src_n = source_counts.get("oauth_tokens", -1)
    oauth_rest_n = restored_counts.get("oauth_tokens", -1)
    gmail_src_n = source_counts.get("processed_gmail_messages", -1)
    gmail_rest_n = restored_counts.get("processed_gmail_messages", -1)
    accepted_src_n = _psql(
        args.container, args.pg_user, args.source_db,
        "SELECT count(*) FROM jobs WHERE eligible_for_owner IS TRUE;",
    )[1]
    accepted_rest_n = _psql(
        args.container, args.pg_user, verify_db,
        "SELECT count(*) FROM jobs WHERE eligible_for_owner IS TRUE;",
    )[1]
    fixture_src_n = source_counts.get("jobs", 0)  # placeholder; compute separately
    _, fixture_raw = _psql(
        args.container, args.pg_user, args.source_db,
        "SELECT count(*) FROM jobs WHERE data_provenance IN ('fixture','test','validation');",
    )

    def _count_val(raw: str) -> int:
        if isinstance(raw, int):
            return raw
        return int((str(raw or "0").strip().splitlines()[0] or "0"))

    accepted_src_n = _count_val(accepted_src_n)
    accepted_rest_n = _count_val(accepted_rest_n)
    fixture_src_n = _count_val(fixture_raw)

    identity_ok = marker_out.strip() == f"OWNER_CANDIDATE|{args.identity_uuid}"
    passed = (
        dump_proc.returncode == 0
        and restore_proc.returncode == 0
        and not mismatches
        and source_tables == restored_tables
        and identity_ok
        and oauth_src_n == oauth_rest_n
        and gmail_src_n == gmail_rest_n
        and accepted_src_n == accepted_rest_n
        and fixture_src_n == 0
    )

    _psql(args.container, args.pg_user, "postgres", f'DROP DATABASE IF EXISTS "{verify_db}";')

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_database": args.source_db,
        "dump_path": str(dump_path),
        "size_bytes": dump_path.stat().st_size,
        "sha256": sha,
        "pg_dump_exit_code": dump_proc.returncode,
    }
    verification = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verification_database": verify_db,
        "restore_exit_code": restore_proc.returncode,
        "schema_match": source_tables == restored_tables,
        "source_table_count": len(source_tables),
        "restored_table_count": len(restored_tables),
        "row_count_mismatches": mismatches,
        "identity_marker": marker_out.strip(),
        "identity_verified": identity_ok,
        "oauth_token_count_source": oauth_src_n,
        "oauth_token_count_restored": oauth_rest_n,
        "processed_gmail_source": gmail_src_n,
        "processed_gmail_restored": gmail_rest_n,
        "accepted_jobs_source": accepted_src_n,
        "accepted_jobs_restored": accepted_rest_n,
        "fixture_rows_source": fixture_src_n,
        "critical_table_counts": {t: source_counts.get(t) for t in CRITICAL_TABLES if t in source_counts},
        "passed": passed,
        "disposable_db_removed": True,
    }
    os.makedirs(os.path.dirname(args.manifest_json) or ".", exist_ok=True)
    with open(args.manifest_json, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    with open(args.verification_json, "w", encoding="utf-8") as fh:
        json.dump(verification, fh, indent=2)
    print(json.dumps({"passed": passed, "sha256": sha}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
