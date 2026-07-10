#!/usr/bin/env python3
"""Reject owner-stack pytest invocation patterns in executable scripts and CI."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IGNORE_DIRS = {".git", "node_modules", ".venv", "private", "__pycache__", ".next", "artifacts"}
SCAN_SUFFIXES = {".ps1", ".sh", ".yml", ".yaml", ".md"}

PATTERNS = [
    re.compile(r"docker\s+compose(?:\s+-f\s+\S+)*\s+exec(?:\s+-T)?\s+api\s+pytest\b", re.I),
    re.compile(r"docker\s+compose(?:\s+-f\s+\S+)*\s+run(?:\s+--rm)?\s+api\s+pytest\b", re.I),
]

ALLOWLIST_PATH_PARTS = {
    "docs/recovery",
    "docs/runbooks",
    "docs/validation",
    "docs/Program",
    "validation",
    "scripts/validation/owner_stack_pytest_scan.py",
    "scripts/local/Run-Aarohan-Tests.ps1",
    "scripts/recovery",
}

NEGATION_PREFIXES = (
    "do not",
    "don't",
    "never",
    "**do not**",
    "not run",
    "blocked",
)


def _is_allowlisted(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    for part in ALLOWLIST_PATH_PARTS:
        if rel == part or rel.startswith(part + "/"):
            return True
    return False


def _line_allowed(line: str) -> bool:
    lower = line.lower()
    return any(prefix in lower for prefix in NEGATION_PREFIXES)


violations: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    if any(part in IGNORE_DIRS for part in path.parts):
        continue
    if path.suffix.lower() not in SCAN_SUFFIXES:
        continue
    if _is_allowlisted(path):
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    rel = path.relative_to(ROOT)
    for idx, line in enumerate(text.splitlines(), start=1):
        if _line_allowed(line):
            continue
        for pattern in PATTERNS:
            if pattern.search(line):
                violations.append(f"{rel}:{idx}: matched {pattern.pattern}")

if violations:
    print("OWNER STACK PYTEST SCAN FAILED")
    for item in violations:
        print(item)
    sys.exit(1)

print("OWNER STACK PYTEST SCAN PASSED")
sys.exit(0)
