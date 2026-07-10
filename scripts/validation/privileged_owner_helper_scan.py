#!/usr/bin/env python3
"""Fail CI when privileged owner helpers lack canonical identity preflight."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCAN_DIRS = [
    ROOT / "scripts" / "local",
    ROOT / "scripts" / "recovery",
    ROOT / "scripts" / "backup",
]

IGNORE_FILES = {
    "Assert-AarohanOwnerDatabaseIdentity.ps1",
    "Assert-RecoveryDatabaseIdentity.ps1",
    "Invoke-ProvisionOwnerDatabase.ps1",
    "Invoke-ProvisionE2EDatabase.ps1",
    "Start-Aarohan-E2E.ps1",
    "Run-Aarohan-Tests.ps1",
    "Invoke-AarohanTestCompose.ps1",
}

GUARD_MARKERS = (
    "Assert-AarohanOwnerDatabaseIdentity",
    "validate_owner_database_identity",
    "owner_database_identity_preflight",
    "Assert-RecoveryDatabaseIdentity",
    "validate_recovery_database_identity",
    "recovery_database_identity_preflight",
)

PRIVILEGED_PATTERNS = [
    re.compile(r"\bpg_dump\b", re.I),
    re.compile(r"\bpg_restore\b", re.I),
    re.compile(r"\bCREATE\s+DATABASE\b", re.I),
    re.compile(r"\bDROP\s+DATABASE\b", re.I),
    re.compile(r"\bDROP\s+SCHEMA\b", re.I),
    re.compile(r"\bTRUNCATE\b", re.I),
    re.compile(r"\bDELETE\s+FROM\b", re.I),
    re.compile(r"\balembic\s+downgrade\b", re.I),
]

E2E_MARKERS = (
    "Invoke-ProvisionE2EDatabase",
    "Invoke-AarohanTestCompose",
    "AAROHAN_DB_IDENTITY_PURPOSE=E2E",
    "AAROHAN_DB_IDENTITY_PURPOSE=CI",
    "career_os_e2e",
    "postgres-e2e",
)


def _is_e2e_or_ci_script(text: str, path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if "docker-compose.test" in text or "Start-Aarohan-E2E" in rel:
        return True
    return any(marker in text for marker in E2E_MARKERS)


def _requires_guard(text: str) -> bool:
    return any(pattern.search(text) for pattern in PRIVILEGED_PATTERNS)


def _has_guard(text: str) -> bool:
    return any(marker in text for marker in GUARD_MARKERS)


violations: list[str] = []
for scan_dir in SCAN_DIRS:
    if not scan_dir.exists():
        continue
    for path in scan_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".ps1", ".py", ".sh"}:
            continue
        if path.name in IGNORE_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not _requires_guard(text):
            continue
        if _is_e2e_or_ci_script(text, path):
            continue
        if _has_guard(text):
            continue
        rel = path.relative_to(ROOT)
        violations.append(f"{rel}: privileged owner helper missing canonical identity guard")

fixture = ROOT / "validation" / "fixtures" / "unguarded_privileged_helper_fixture.ps1"
if fixture.exists():
    fixture_text = fixture.read_text(encoding="utf-8", errors="ignore")
    if _requires_guard(fixture_text) and not _has_guard(fixture_text):
        pass  # expected unguarded fixture for unit test
    else:
        violations.append(f"{fixture.relative_to(ROOT)}: fixture must remain unguarded for scan test")

if violations:
    print("PRIVILEGED OWNER HELPER SCAN FAILED")
    for item in violations:
        print(item)
    sys.exit(1)

print("PRIVILEGED OWNER HELPER SCAN PASSED")
sys.exit(0)
