#!/usr/bin/env python3
"""Execute guarded canonical owner cutover with rollback on failure."""

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
    PURPOSE_OWNER,
    PURPOSE_OWNER_CANDIDATE,
    validate_database_identity_marker,
)
from promote_database_identity_marker import promote_marker

REQUIRED_PHRASE = "APPROVE OWNER CANDIDATE CUTOVER"
KEY_TABLES = ["jobs", "applications", "oauth_tokens", "users", "processed_gmail_messages"]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _psql(container: str, user: str, db: str, sql: str) -> tuple[int, str]:
    proc = _run([
        "docker", "exec", container,
        "psql", "-U", user, "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql,
    ])
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _psql_at(container: str, user: str, sql: str) -> tuple[int, str]:
    return _psql(container, user, "postgres", sql)


def _terminate_connections(container: str, user: str, db: str) -> None:
    _psql_at(
        container,
        user,
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db}' AND pid <> pg_backend_pid();",
    )


def _scalar(container: str, user: str, db: str, sql: str) -> tuple[int, str]:
    proc = _run(["docker", "exec", container, "psql", "-U", user, "-d", db, "-Atc", sql])
    return proc.returncode, (proc.stdout or "").strip()


def _row_counts(container: str, user: str, db: str) -> dict[str, int | str]:
    counts: dict[str, int | str] = {}
    for table in KEY_TABLES:
        code, out = _scalar(container, user, db, f"SELECT count(*) FROM {table};")
        counts[table] = int(out) if code == 0 and out.isdigit() else -1
    code, out = _scalar(
        container,
        user,
        db,
        "SELECT purpose||'|'||identity_uuid FROM aarohan_meta.database_identity LIMIT 1;",
    )
    counts["identity_marker"] = out if code == 0 else "unknown"
    return counts


def _dump_db(container: str, user: str, db: str, path: Path) -> tuple[int, str]:
    cpath = f"/tmp/phase4_{db}.sql"
    proc = _run([
        "docker", "exec", container,
        "pg_dump", "-U", user, "-d", db, "-Fp", "--no-owner", "--no-acl", "-f", cpath,
    ])
    if proc.returncode != 0:
        return proc.returncode, proc.stderr or proc.stdout or ""
    cp = _run(["docker", "cp", f"{container}:{cpath}", str(path)])
    _run(["docker", "exec", container, "rm", "-f", cpath])
    return cp.returncode, cp.stderr or ""


def _rename_db(container: str, user: str, old: str, new: str) -> tuple[int, str]:
    _terminate_connections(container, user, old)
    return _psql_at(container, user, f'ALTER DATABASE "{old}" RENAME TO "{new}";')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 4 guarded owner cutover")
    parser.add_argument("--container", default="aarohan-careeros-postgres-1")
    parser.add_argument("--pg-user", default="career_os")
    parser.add_argument("--pg-password", default=os.environ.get("POSTGRES_PASSWORD", ""))
    parser.add_argument("--candidate-uuid", required=True)
    parser.add_argument("--confirmation-phrase", default=os.environ.get("CUTOVER_APPROVAL_PHRASE", ""))
    parser.add_argument("--destructive-token", default=os.environ.get("AAROHAN_DESTRUCTIVE_TOKEN", ""))
    parser.add_argument("--new-owner-uuid", default="")
    parser.add_argument("--dumps-dir", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    if args.confirmation_phrase != REQUIRED_PHRASE:
        print(json.dumps({"error": f"Confirmation phrase must be: {REQUIRED_PHRASE}"}), file=sys.stderr)
        return 2

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rollback_db = f"career_os_rollback_{ts}"[:63]
    new_owner_uuid = args.new_owner_uuid or str(uuid.uuid4())
    dumps_dir = Path(args.dumps_dir)
    dumps_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "confirmation_phrase": REQUIRED_PHRASE,
        "candidate_uuid": args.candidate_uuid,
        "new_owner_uuid": new_owner_uuid,
        "rollback_database": rollback_db,
        "steps": [],
        "passed": False,
    }

    def step(name: str, ok: bool, **extra) -> None:
        manifest["steps"].append({"step": name, "ok": ok, **extra})
        if not ok:
            raise RuntimeError(f"Cutover step failed: {name}")

    try:
        canonical_before = _row_counts(args.container, args.pg_user, "career_os")
        candidate_before = _row_counts(args.container, args.pg_user, "career_os_owner_candidate")
        manifest["before_manifest"] = {
            "career_os": canonical_before,
            "career_os_owner_candidate": candidate_before,
        }
        step("before_manifest", True)

        owner_dump = dumps_dir / f"career_os_precutover_{ts}.sql"
        candidate_dump = dumps_dir / f"career_os_owner_candidate_precutover_{ts}.sql"
        code, err = _dump_db(args.container, args.pg_user, "career_os", owner_dump)
        step("backup_damaged_owner", code == 0 and owner_dump.is_file(), sha256=_sha256(owner_dump) if owner_dump.is_file() else None, error=err[:200] if code != 0 else None)
        code, err = _dump_db(args.container, args.pg_user, "career_os_owner_candidate", candidate_dump)
        step("backup_candidate", code == 0 and candidate_dump.is_file(), sha256=_sha256(candidate_dump) if candidate_dump.is_file() else None, error=err[:200] if code != 0 else None)

        code, err = _rename_db(args.container, args.pg_user, "career_os", rollback_db)
        step("archive_damaged_owner", code == 0, rollback_database=rollback_db, error=err[:200] if code != 0 else None)

        renamed_candidate = False
        try:
            code, err = _rename_db(args.container, args.pg_user, "career_os_owner_candidate", "career_os")
            step("promote_candidate_rename", code == 0, error=err[:200] if code != 0 else None)
            renamed_candidate = True

            bootstrap_url = f"postgresql+psycopg://{args.pg_user}:{args.pg_password}@127.0.0.1:5432/career_os"
            promotion = promote_marker(
                bootstrap_url,
                candidate_uuid=args.candidate_uuid,
                new_owner_uuid=new_owner_uuid,
                confirmation_phrase=args.confirmation_phrase,
                destructive_token=args.destructive_token,
            )
            step("identity_promoted_to_owner", promotion.get("promoted") is True, new_owner_uuid=new_owner_uuid)

            os.environ["AAROHAN_DB_IDENTITY_PURPOSE"] = PURPOSE_OWNER
            os.environ["AAROHAN_DB_IDENTITY_UUID"] = new_owner_uuid
            bootstrap_engine = create_engine(bootstrap_url, pool_pre_ping=True)
            try:
                validate_database_identity_marker(bootstrap_engine, bootstrap_url)
                owner_ok = True
            except Exception:
                owner_ok = False
            finally:
                bootstrap_engine.dispose()
            step("owner_marker_validates", owner_ok)

            os.environ["AAROHAN_DB_IDENTITY_PURPOSE"] = PURPOSE_OWNER_CANDIDATE
            os.environ["AAROHAN_DB_IDENTITY_UUID"] = args.candidate_uuid
            bootstrap_engine = create_engine(bootstrap_url, pool_pre_ping=True)
            try:
                validate_database_identity_marker(bootstrap_engine, bootstrap_url)
                candidate_fail = False
            except Exception:
                candidate_fail = True
            finally:
                bootstrap_engine.dispose()
            step("candidate_marker_rejected", candidate_fail)

            rollback_oauth = _row_counts(args.container, args.pg_user, rollback_db)["oauth_tokens"]
            step(
                "rollback_oauth_preserved",
                rollback_oauth == canonical_before["oauth_tokens"],
                rollback_oauth_count=rollback_oauth,
                expected=canonical_before["oauth_tokens"],
            )

            after = _row_counts(args.container, args.pg_user, "career_os")
            manifest["after_manifest"] = {"career_os": after}
            step(
                "after_manifest",
                str(after.get("identity_marker", "")).upper().startswith(f"OWNER|{new_owner_uuid}".upper()),
                identity_marker=after.get("identity_marker"),
            )
            manifest["passed"] = True
        except Exception:
            if renamed_candidate:
                repair_url = f"postgresql+psycopg://{args.pg_user}:{args.pg_password}@127.0.0.1:5432/career_os"
                repair_engine = create_engine(repair_url)
                try:
                    with repair_engine.connect() as conn:
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
                            {"purpose": PURPOSE_OWNER_CANDIDATE, "uuid": args.candidate_uuid},
                        )
                        conn.execute(text("ALTER TABLE aarohan_meta.database_identity ENABLE TRIGGER trg_database_identity_immutable"))
                finally:
                    repair_engine.dispose()
                _rename_db(args.container, args.pg_user, "career_os", "career_os_owner_candidate")
            _rename_db(args.container, args.pg_user, rollback_db, "career_os")
            raise
    except Exception as exc:
        manifest["error"] = str(exc)[:500]
        manifest["passed"] = False

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(json.dumps({"passed": manifest["passed"], "new_owner_uuid": new_owner_uuid, "rollback_database": rollback_db}))
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
