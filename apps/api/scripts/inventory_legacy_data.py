"""CLI: inventory legacy fixture/test data and optional provenance backfill."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.database import SessionLocal
from app.services.legacy_data_inventory import apply_provenance_backfill, build_inventory, format_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory legacy fixture/test data")
    parser.add_argument(
        "--report-dir",
        default=str(Path(__file__).resolve().parents[1] / "generated" / "cleanup-reports"),
    )
    parser.add_argument("--backfill", action="store_true", help="Apply provenance tags only (no deletes)")
    parser.add_argument("--stdout", action="store_true", help="Print report to stdout")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        inventory = build_inventory(db)
        if args.backfill:
            count = apply_provenance_backfill(db, inventory)
            inventory = build_inventory(db)
            print(f"Backfilled provenance on {count} record(s)")
        report = format_report(inventory)
        report_dir = Path(args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = report_dir / f"legacy-inventory-dryrun-{stamp}.txt"
        path.write_text(report, encoding="utf-8")
        print(f"Report written: {path}")
        if args.stdout:
            print(report)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
