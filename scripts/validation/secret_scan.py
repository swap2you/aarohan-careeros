#!/usr/bin/env python3
"""Scan repository for likely secrets."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IGNORE_DIRS = {".git", "node_modules", ".venv", "private", "__pycache__", ".next", "artifacts", ".local", "docs/archive"}
SKIP_FILES = {"google-oauth-client.json", "LOCAL-CREDENTIALS.private.md"}
SKIP_NAME_PATTERNS = [
    re.compile(r"keys.*secrets", re.I),
    re.compile(r"\.zip$", re.I),
    re.compile(r"LOCAL-CREDENTIALS\.private\.md$", re.I),
]
PATTERNS = [
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"password\s*=\s*['\"][^'\"]{8,}['\"]", re.I),
]

violations: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    if any(part in IGNORE_DIRS for part in path.parts):
        continue
    if path.name in SKIP_FILES:
        continue
    if any(p.search(path.name) for p in SKIP_NAME_PATTERNS):
        continue
    if path.suffix in {".png", ".jpg", ".pdf", ".woff", ".woff2"}:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    for pattern in PATTERNS:
        if pattern.search(text):
            violations.append(f"{path.relative_to(ROOT)}: matched {pattern.pattern}")

if violations:
    print("SECRET SCAN FAILED")
    for item in violations:
        print(item)
    sys.exit(1)

print("SECRET SCAN PASSED")
sys.exit(0)
