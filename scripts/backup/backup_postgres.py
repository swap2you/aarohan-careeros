#!/usr/bin/env python3
"""Backup PostgreSQL database to local archive."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "backups"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
output = BACKUP_DIR / f"career_os_{timestamp}.sql"

cmd = [
    "pg_dump",
    "-h",
    os.environ.get("PGHOST", "localhost"),
    "-U",
    os.environ.get("PGUSER", "career_os"),
    "-d",
    os.environ.get("PGDATABASE", "career_os"),
    "-f",
    str(output),
]

print("Running backup:", " ".join(cmd))
subprocess.run(cmd, check=True)
print(f"Backup written to {output}")
