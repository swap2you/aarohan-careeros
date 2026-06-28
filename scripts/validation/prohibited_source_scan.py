#!/usr/bin/env python3
"""Ensure prohibited automation patterns are not present."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IGNORE_DIRS = {".git", "node_modules", ".venv", "private", "__pycache__", ".next"}
PROHIBITED = [
    re.compile(r"linkedin.*scrap", re.I),
    re.compile(r"indeed.*scrap", re.I),
    re.compile(r"captcha.*bypass", re.I),
    re.compile(r"submit-external", re.I),
    re.compile(r"mass_auto_apply", re.I),
]
ALLOWLIST_PATH_PARTS = {
    "docs",
    "validation",
    "prompts",
    "config",
    "tests",
    "test_core.py",
    "AGENTS.md",
    "SECURITY",
    "source-policy",
    "README.md",
    "Aarohan_R1_Local_Execution_Pack_v2",
}

violations: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    if any(part in IGNORE_DIRS for part in path.parts):
        continue
    if any(part in ALLOWLIST_PATH_PARTS for part in path.parts):
        continue
    if path.suffix not in {".py", ".ts", ".tsx", ".js", ".yml", ".yaml", ".md"}:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern in PROHIBITED:
        if pattern.search(text):
            violations.append(f"{path.relative_to(ROOT)}: matched {pattern.pattern}")

if violations:
    print("PROHIBITED SOURCE SCAN FAILED")
    for item in violations:
        print(item)
    sys.exit(1)

print("PROHIBITED SOURCE SCAN PASSED")
sys.exit(0)
