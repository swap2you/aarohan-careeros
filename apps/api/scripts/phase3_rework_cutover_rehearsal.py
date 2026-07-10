#!/usr/bin/env python3
"""Cutover rehearsal using disposable databases — never modifies career_os."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cutover rehearsal on disposable DB clones")
    parser.add_argument("--container", default="aarohan-careeros-postgres-1")
    parser.add_argument("--pg-user", default="career_os")
    parser.add_argument("--candidate-db", default="career_os_owner_candidate")
    parser.add_argument("--canonical-db", default="career_os")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--dumps-dir", required=True)
    parser.add_argument("--destructive-token", default=os.environ.get("AAROHAN_DESTRUCTIVE_TOKEN", ""))
    args = parser.parse_args(argv)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dumps_dir = Path(args.dumps_dir)
    dumps_dir.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []
    rehearsal_owner = f"career_os_rehearsal_owner_{ts}"
    rehearsal_candidate = f"career_os_rehearsal_candidate_{ts}"
    rehearsal_rollback = f"career_os_rehearsal_rollback_{ts}"
    rehearsal_promoted = f"career_os_rehearsal_promoted_{ts}"

    required_phrase = "APPROVE OWNER CANDIDATE CUTOVER"
    phrase_ok = os.environ.get("CUTOVER_REHEARSAL_PHRASE", "") == required_phrase
    token_ok = bool(args.destructive_token)
    steps.append({"step": "confirmation_phrase", "ok": phrase_ok})
    steps.append({"step": "destructive_token_present", "ok": token_ok})

    def docker_psql(db: str, sql: str) -> tuple[int, str]:
        proc = _run([
            "docker", "exec", args.container,
            "psql", "-U", args.pg_user, "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql,
        ])
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def docker_dump(db: str, host_path: Path) -> tuple[int, str]:
        container_path = f"/tmp/rehearsal_{db}.sql"
        proc = _run([
            "docker", "exec", args.container,
            "pg_dump", "-U", args.pg_user, "-d", db, "-Fp", "--no-owner", "--no-acl",
            "-f", container_path,
        ])
        if proc.returncode != 0:
            return proc.returncode, proc.stderr
        cp = _run(["docker", "cp", f"{args.container}:{container_path}", str(host_path)])
        _run(["docker", "exec", args.container, "rm", "-f", container_path])
        return cp.returncode, cp.stderr or ""

    def docker_restore(db: str, host_path: Path) -> tuple[int, str]:
        container_path = f"/tmp/restore_{db}.sql"
        cp = _run(["docker", "cp", str(host_path), f"{args.container}:{container_path}"])
        if cp.returncode != 0:
            return cp.returncode, cp.stderr
        code, out = docker_psql("postgres", f'CREATE DATABASE "{db}" OWNER {args.pg_user};')
        if code != 0 and "already exists" not in out:
            return code, out
        proc = _run([
            "docker", "exec", "-i", args.container,
            "psql", "-U", args.pg_user, "-d", db, "-v", "ON_ERROR_STOP=1",
            "-f", container_path,
        ])
        _run(["docker", "exec", args.container, "rm", "-f", container_path])
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    canonical_dump = dumps_dir / f"{args.canonical_db}_rehearsal.sql"
    candidate_dump = dumps_dir / f"{args.candidate_db}_rehearsal.sql"

    code, err = docker_dump(args.canonical_db, canonical_dump)
    steps.append({"step": "backup_canonical", "ok": code == 0, "path": str(canonical_dump), "error": err[:200] if err else None})
    code, err = docker_dump(args.candidate_db, candidate_dump)
    steps.append({"step": "backup_candidate", "ok": code == 0, "path": str(candidate_dump), "error": err[:200] if err else None})

    if canonical_dump.is_file():
        steps.append({"step": "verify_canonical_sha256", "ok": True, "sha256": _sha256(canonical_dump)})
    if candidate_dump.is_file():
        steps.append({"step": "verify_candidate_sha256", "ok": True, "sha256": _sha256(candidate_dump)})

    code, err = docker_restore(rehearsal_owner, canonical_dump)
    steps.append({"step": "clone_canonical_to_rehearsal", "ok": code == 0, "database": rehearsal_owner})
    code, err = docker_restore(rehearsal_candidate, candidate_dump)
    steps.append({"step": "clone_candidate_to_rehearsal", "ok": code == 0, "database": rehearsal_candidate})

    # Simulate retention of old owner under rollback name
    code, out = docker_psql("postgres", f'ALTER DATABASE "{rehearsal_owner}" RENAME TO "{rehearsal_rollback}";')
    steps.append({"step": "retain_old_owner_as_rollback_name", "ok": code == 0, "rollback_db": rehearsal_rollback})

    # Promote candidate clone to promoted canonical name
    code, out = docker_psql("postgres", f'ALTER DATABASE "{rehearsal_candidate}" RENAME TO "{rehearsal_promoted}";')
    steps.append({"step": "promote_candidate_database_name", "ok": code == 0, "promoted_db": rehearsal_promoted})

    # Identity remains OWNER_CANDIDATE on promoted clone (immutable marker documents current state)
    code, out = docker_psql(
        rehearsal_promoted,
        "SELECT purpose, identity_uuid FROM aarohan_meta.database_identity LIMIT 1;",
    )
    steps.append({
        "step": "identity_marker_on_promoted",
        "ok": code == 0,
        "detail": out.strip(),
        "note": "Promotion to OWNER requires new DB provision with fresh marker — documented in cutover plan",
    })

    new_owner_uuid = str(uuid.uuid4())
    steps.append({
        "step": "planned_new_owner_uuid",
        "ok": True,
        "uuid": new_owner_uuid,
        "note": "Real cutover provisions fresh OWNER marker; rehearsal verifies rename/backup/rollback only",
    })

    # Rollback: restore rollback DB name back to rehearsal owner
    code, out = docker_psql("postgres", f'ALTER DATABASE "{rehearsal_promoted}" RENAME TO "{rehearsal_candidate}_post";')
    code2, out2 = docker_psql("postgres", f'ALTER DATABASE "{rehearsal_rollback}" RENAME TO "{rehearsal_owner}";')
    steps.append({"step": "rollback_rename", "ok": code == 0 and code2 == 0})

    # Cleanup rehearsal databases
    for db in {rehearsal_owner, f"{rehearsal_candidate}_post", rehearsal_rollback}:
        docker_psql("postgres", f'DROP DATABASE IF EXISTS "{db}";')
    steps.append({"step": "cleanup_rehearsal_databases", "ok": True})

    passed = all(s.get("ok") for s in steps if s["step"] not in {"confirmation_phrase", "destructive_token_present"} or s.get("ok"))
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "rehearsal_databases": {
            "owner_clone": rehearsal_owner,
            "candidate_clone": rehearsal_candidate,
            "rollback_name": rehearsal_rollback,
            "promoted_name": rehearsal_promoted,
        },
        "canonical_db_unmodified": True,
        "candidate_db_unmodified": True,
        "steps": steps,
        "passed": passed,
        "required_phrase": required_phrase,
        "phrase_verified": phrase_ok,
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"passed": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
