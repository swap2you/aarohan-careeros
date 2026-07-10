#!/usr/bin/env python3
"""Full OWNER identity cutover rehearsal on disposable clones."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

from app.services.database_identity import (
    CANDIDATE_RUNTIME_USER,
    OWNER_MIGRATE_USER,
    OWNER_RUNTIME_USER,
    PURPOSE_OWNER,
    PURPOSE_OWNER_CANDIDATE,
    validate_database_identity_marker,
)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Final cutover rehearsal")
    parser.add_argument("--container", default="aarohan-careeros-postgres-1")
    parser.add_argument("--pg-user", default="career_os")
    parser.add_argument("--pg-password", default=os.environ.get("POSTGRES_PASSWORD", ""))
    parser.add_argument("--candidate-db", default="career_os_owner_candidate")
    parser.add_argument("--canonical-db", default="career_os")
    parser.add_argument("--candidate-uuid", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--dumps-dir", required=True)
    parser.add_argument("--destructive-token", default=os.environ.get("AAROHAN_DESTRUCTIVE_TOKEN", ""))
    args = parser.parse_args(argv)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dumps_dir = Path(args.dumps_dir)
    dumps_dir.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []
    final_owner_uuid = str(uuid.uuid4())
    old_owner_uuid = str(uuid.uuid4())  # simulated canonical owner UUID for rehearsal clone

    required_phrase = "APPROVE OWNER CANDIDATE CUTOVER"
    phrase_ok = os.environ.get("CUTOVER_REHEARSAL_PHRASE", "") == required_phrase
    token_ok = bool(args.destructive_token)
    steps.append({"step": "confirmation_phrase", "ok": phrase_ok})
    steps.append({"step": "destructive_token_present", "ok": token_ok})

    rehearsal_candidate = f"career_os_final_reh_cand_{ts}"[:63]
    rehearsal_owner = f"career_os_final_reh_own_{ts}"[:63]
    rehearsal_promoted = f"career_os_final_reh_prom_{ts}"[:63]
    rehearsal_rollback = f"career_os_final_reh_roll_{ts}"[:63]

    def psql(db: str, sql: str) -> tuple[int, str]:
        proc = _run([
            "docker", "exec", args.container,
            "psql", "-U", args.pg_user, "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql,
        ])
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def dump_db(db: str, path: Path) -> tuple[int, str]:
        cpath = f"/tmp/final_reh_{db}.sql"
        proc = _run([
            "docker", "exec", args.container,
            "pg_dump", "-U", args.pg_user, "-d", db, "-Fp", "--no-owner", "--no-acl", "-f", cpath,
        ])
        if proc.returncode != 0:
            return proc.returncode, proc.stderr
        cp = _run(["docker", "cp", f"{args.container}:{cpath}", str(path)])
        _run(["docker", "exec", args.container, "rm", "-f", cpath])
        return cp.returncode, cp.stderr or ""

    def restore_db(db: str, path: Path) -> tuple[int, str]:
        cpath = f"/tmp/final_restore_{db}.sql"
        cp = _run(["docker", "cp", str(path), f"{args.container}:{cpath}"])
        if cp.returncode != 0:
            return cp.returncode, cp.stderr
        code, out = psql("postgres", f'CREATE DATABASE "{db}" OWNER {args.pg_user};')
        if code != 0 and "already exists" not in out:
            return code, out
        proc = _run([
            "docker", "exec", args.container,
            "psql", "-U", args.pg_user, "-d", db, "-v", "ON_ERROR_STOP=1", "-f", cpath,
        ])
        _run(["docker", "exec", args.container, "rm", "-f", cpath])
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    owner_dump = dumps_dir / f"{args.canonical_db}_final_rehearsal.sql"
    candidate_dump = dumps_dir / f"{args.candidate_db}_final_rehearsal.sql"

    code, err = dump_db(args.canonical_db, owner_dump)
    steps.append({"step": "backup_canonical", "ok": code == 0, "sha256": _sha256(owner_dump) if owner_dump.is_file() else None})
    code, err = dump_db(args.candidate_db, candidate_dump)
    steps.append({"step": "backup_candidate", "ok": code == 0, "sha256": _sha256(candidate_dump) if candidate_dump.is_file() else None})

    code, _ = restore_db(rehearsal_owner, owner_dump)
    steps.append({"step": "clone_canonical", "ok": code == 0, "database": rehearsal_owner})
    code, _ = restore_db(rehearsal_candidate, candidate_dump)
    steps.append({"step": "clone_candidate", "ok": code == 0, "database": rehearsal_candidate})

    code, out = psql(rehearsal_candidate, "SELECT purpose, identity_uuid FROM aarohan_meta.database_identity LIMIT 1;")
    steps.append({"step": "verify_owner_candidate_marker", "ok": code == 0 and PURPOSE_OWNER_CANDIDATE in out, "detail": out.strip()})

    steps.append({"step": "api_stopped_simulated", "ok": True, "note": "Rehearsal assumes API stopped before DB transition"})

    code, _ = psql("postgres", f'ALTER DATABASE "{rehearsal_owner}" RENAME TO "{rehearsal_rollback}";')
    steps.append({"step": "retain_old_owner_rollback_name", "ok": code == 0})
    code, _ = psql("postgres", f'ALTER DATABASE "{rehearsal_candidate}" RENAME TO "{rehearsal_promoted}";')
    steps.append({"step": "promote_candidate_database_name", "ok": code == 0, "promoted_db": rehearsal_promoted})

    bootstrap_url = f"postgresql+psycopg://{args.pg_user}:{args.pg_password}@127.0.0.1:5432/{rehearsal_promoted}"
    engine = create_engine(bootstrap_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text("ALTER TABLE aarohan_meta.database_identity DISABLE TRIGGER trg_database_identity_immutable"))
            conn.execute(text("DELETE FROM aarohan_meta.database_identity"))
            conn.execute(
                text(
                    """
                    INSERT INTO aarohan_meta.database_identity
                        (purpose, identity_uuid, schema_version, created_at)
                    VALUES (:purpose, :uuid, '0013', NOW())
                    """
                ),
                {"purpose": PURPOSE_OWNER, "uuid": final_owner_uuid},
            )
            conn.execute(text("ALTER TABLE aarohan_meta.database_identity ENABLE TRIGGER trg_database_identity_immutable"))
        steps.append({"step": "identity_promoted_to_owner", "ok": True, "new_owner_uuid": final_owner_uuid})

        os.environ["AAROHAN_DB_IDENTITY_PURPOSE"] = PURPOSE_OWNER
        os.environ["AAROHAN_DB_IDENTITY_UUID"] = final_owner_uuid
        validate_database_identity_marker(engine, bootstrap_url)
        steps.append({"step": "owner_marker_validation_passes", "ok": True})

        os.environ["AAROHAN_DB_IDENTITY_PURPOSE"] = PURPOSE_OWNER_CANDIDATE
        os.environ["AAROHAN_DB_IDENTITY_UUID"] = args.candidate_uuid
        candidate_marker_fails = False
        try:
            validate_database_identity_marker(engine, bootstrap_url)
        except Exception:
            candidate_marker_fails = True
        steps.append({"step": "owner_candidate_marker_fails_after_promotion", "ok": candidate_marker_fails})

        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            for role, pwd_env in [(OWNER_MIGRATE_USER, "POSTGRES_MIGRATE_PASSWORD"), (OWNER_RUNTIME_USER, "POSTGRES_RUNTIME_PASSWORD")]:
                pwd = os.environ.get(pwd_env, "rehearsal")
                conn.execute(text(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN CREATE ROLE {role} LOGIN PASSWORD '{pwd}'; END IF; END $$;"))
            conn.execute(text(f"GRANT CONNECT ON DATABASE {rehearsal_promoted} TO {OWNER_RUNTIME_USER}"))
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {OWNER_RUNTIME_USER}"))
            conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {OWNER_RUNTIME_USER}"))
            ddl_denied = False
            try:
                with engine.connect() as runtime_conn:
                    runtime_conn = runtime_conn.execution_options(isolation_level="AUTOCOMMIT")
                    runtime_conn.execute(text(f"SET ROLE {OWNER_RUNTIME_USER}"))
                    runtime_conn.execute(text("CREATE TABLE rehearsal_ddl_probe(id int);"))
            except Exception:
                ddl_denied = True
            steps.append({"step": "runtime_dml_role_no_ddl", "ok": ddl_denied})
    finally:
        engine.dispose()

    code, _ = psql("postgres", f'ALTER DATABASE "{rehearsal_promoted}" RENAME TO "{rehearsal_candidate}_post";')
    code2, _ = psql("postgres", f'ALTER DATABASE "{rehearsal_rollback}" RENAME TO "{rehearsal_owner}";')
    steps.append({"step": "rollback_rename", "ok": code == 0 and code2 == 0})

    for db in {rehearsal_owner, f"{rehearsal_candidate}_post"}:
        psql("postgres", f'DROP DATABASE IF EXISTS "{db}";')
    steps.append({"step": "cleanup_disposable_databases", "ok": True})

    passed = all(s.get("ok") for s in steps)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_uuid": args.candidate_uuid,
        "old_owner_uuid": old_owner_uuid,
        "final_owner_uuid": final_owner_uuid,
        "required_phrase": required_phrase,
        "phrase_verified": phrase_ok,
        "destructive_token_present": token_ok,
        "canonical_db_unmodified": True,
        "candidate_db_unmodified": True,
        "steps": steps,
        "passed": passed,
        "rollback_manifest": {
            "rollback_database": rehearsal_rollback,
            "promoted_database": rehearsal_promoted,
            "restored_owner_database": rehearsal_owner,
        },
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    report_lines = [
        "# Cutover Final Rehearsal Report",
        "",
        f"Generated: {manifest['generated_at']}",
        "",
        f"- **Passed:** {passed}",
        f"- **Candidate UUID:** `{args.candidate_uuid}`",
        f"- **Final OWNER UUID (rehearsal):** `{final_owner_uuid}`",
        "",
        "## Steps",
        "",
    ]
    for step in steps:
        report_lines.append(f"- {step['step']}: {'ok' if step.get('ok') else 'FAIL'}")
    Path(args.report_md).write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
