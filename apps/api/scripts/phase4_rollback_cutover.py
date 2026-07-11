#!/usr/bin/env python3
"""Rollback failed Phase 4 cutover using archived damaged owner database."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

REQUIRED_PHRASE = "APPROVE OWNER CANDIDATE CUTOVER"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _psql_at(container: str, user: str, sql: str) -> tuple[int, str]:
    proc = _run([
        "docker", "exec", container,
        "psql", "-U", user, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", sql,
    ])
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _terminate(container: str, user: str, db: str) -> None:
    _psql_at(
        container,
        user,
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db}' AND pid <> pg_backend_pid();",
    )


def _rename(container: str, user: str, old: str, new: str) -> tuple[int, str]:
    _terminate(container, user, old)
    return _psql_at(container, user, f'ALTER DATABASE "{old}" RENAME TO "{new}";')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rollback Phase 4 cutover")
    parser.add_argument("--container", default="aarohan-careeros-postgres-1")
    parser.add_argument("--pg-user", default="career_os")
    parser.add_argument("--rollback-database", required=True)
    parser.add_argument("--old-owner-uuid", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    failed_db = f"career_os_failed_promotion_{ts}"[:63]
    steps: list[dict] = []
    passed = False

    try:
        code, err = _rename(args.container, args.pg_user, "career_os", failed_db)
        steps.append({"step": "quarantine_failed_promotion", "ok": code == 0, "database": failed_db})
        if code != 0:
            raise RuntimeError(err)

        code, err = _rename(args.container, args.pg_user, args.rollback_database, "career_os")
        steps.append({"step": "restore_archived_owner", "ok": code == 0})
        if code != 0:
            raise RuntimeError(err)

        passed = True
    except Exception as exc:
        steps.append({"step": "error", "ok": False, "detail": str(exc)[:300]})

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rollback_database_restored": args.rollback_database,
        "failed_promotion_database": failed_db if passed else None,
        "old_owner_uuid": args.old_owner_uuid,
        "steps": steps,
        "passed": passed,
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(json.dumps({"passed": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
