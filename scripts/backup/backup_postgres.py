#!/usr/bin/env python3
"""Backup PostgreSQL database to local archive."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.owner_database_identity_preflight import (  # noqa: E402
    OwnerIdentityPreflightError,
    validate_owner_database_identity,
)


def _ensure_owner_identity_env() -> None:
    owner_uuid = (os.getenv("AAROHAN_OWNER_DB_IDENTITY_UUID") or "").strip()
    if owner_uuid:
        os.environ["AAROHAN_DB_IDENTITY_PURPOSE"] = "OWNER"
        os.environ["AAROHAN_DB_IDENTITY_UUID"] = owner_uuid
        return
    if not (os.getenv("AAROHAN_DB_IDENTITY_PURPOSE") or "").strip() and (
        os.getenv("AAROHAN_DB_IDENTITY_UUID") or os.getenv("AAROHAN_OWNER_DB_IDENTITY_UUID")
    ):
        os.environ["AAROHAN_DB_IDENTITY_PURPOSE"] = "OWNER"


def _bootstrap_url() -> str:
    host = os.environ.get("PGHOST", "127.0.0.1")
    port = int(os.environ.get("PGPORT", "5432"))
    user = os.environ.get("PGUSER", "career_os")
    password = os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD", "")
    database = os.environ.get("PGDATABASE", "career_os")
    if not password:
        raise RuntimeError("PGPASSWORD or POSTGRES_PASSWORD required")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def main() -> int:
    _ensure_owner_identity_env()

    database = os.environ.get("PGDATABASE", "career_os")
    host = os.environ.get("PGHOST", "127.0.0.1")
    port = int(os.environ.get("PGPORT", "5432"))
    user = os.environ.get("PGUSER", "career_os")
    compose_project = os.environ.get("COMPOSE_PROJECT_NAME", "aarohan-careeros")
    postgres_service = os.environ.get("AAROHAN_POSTGRES_SERVICE", "postgres")
    postgres_container = os.environ.get("AAROHAN_POSTGRES_CONTAINER", "aarohan-careeros-postgres-1")

    try:
        validate_owner_database_identity(
            database_url=_bootstrap_url(),
            database=database,
            compose_project=compose_project,
            postgres_service=postgres_service,
            postgres_container=postgres_container,
            host=host,
            port=port,
            privileged_user=user,
        )
    except OwnerIdentityPreflightError as exc:
        print(f"Owner identity preflight failed: {exc}", file=sys.stderr)
        return 1

    backup_dir = Path(os.environ.get("BACKUP_DIR", "backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output = backup_dir / f"career_os_{timestamp}.sql"

    cmd = [
        "pg_dump",
        "-h",
        host,
        "-U",
        user,
        "-d",
        database,
        "-f",
        str(output),
    ]
    env = {**os.environ}
    env.setdefault("PGPASSWORD", os.environ.get("POSTGRES_PASSWORD", ""))
    print("Running backup after owner_database_identity_preflight verification")
    subprocess.run(cmd, check=True, env=env)
    print(f"Backup written to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
