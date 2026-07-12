#!/usr/bin/env python3
"""Workflow 01.5 — dump read-only discovery evidence JSON (inventory, policy, preset preview).

Emits, to the given output directory:
- DISCOVERY-SOURCE-INVENTORY.json
- DISCOVERY-POLICY-DEFAULTS.json
- DISCOVERY-POLICY-EFFECTIVE.json
- DISCOVERY-PRESET-PREVIEW.json  (strict/balanced/broad previews against existing records)
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime


def _write(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump discovery evidence JSON")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    os.makedirs(args.output_dir, exist_ok=True)

    from app.database import SessionLocal
    from app.services import discovery_policy_service as pol
    from app.services.discovery_policy import discovery_policy_defaults, job_discovery_policy
    from app.services.discovery_source_inventory import build_source_inventory

    db = SessionLocal()
    try:
        _write(os.path.join(args.output_dir, "DISCOVERY-SOURCE-INVENTORY.json"), build_source_inventory(db))
        _write(os.path.join(args.output_dir, "DISCOVERY-POLICY-DEFAULTS.json"), {"policy": discovery_policy_defaults()})
        _write(os.path.join(args.output_dir, "DISCOVERY-POLICY-EFFECTIVE.json"), {"policy": job_discovery_policy()})
        now = datetime.utcnow()
        preset_preview = {"generated_at": now.isoformat(), "presets": {}}
        for name in pol.preset_names():
            preset_preview["presets"][name] = pol.preview_policy(
                db, pol.preset_overrides(name), sample_limit=6, now=now
            )
        _write(os.path.join(args.output_dir, "DISCOVERY-PRESET-PREVIEW.json"), preset_preview)
    finally:
        db.close()
    print(f"wrote discovery evidence to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
