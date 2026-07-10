#!/usr/bin/env python3
"""Classify recovery staging rows for Phase 3 owner candidate build."""

from __future__ import annotations

import argparse
import json
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity
from app.services.recovery_row_classification import build_recovery_classification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3 row classification")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)

    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        payload = build_recovery_classification(db)
    finally:
        db.close()
        engine.dispose()

    os.makedirs(args.output_dir, exist_ok=True)
    recovery_path = os.path.join(args.output_dir, "ROW-RECOVERY-MANIFEST.json")
    exclusion_path = os.path.join(args.output_dir, "ROW-EXCLUSION-MANIFEST.json")
    ambiguous_path = os.path.join(args.output_dir, "AMBIGUOUS-ROWS-REPORT.md")

    with open(recovery_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_at": payload["generated_at"],
                "summary_by_classification": payload["summary_by_classification"],
                "rows": payload["recovery_manifest"],
            },
            fh,
            indent=2,
        )
    with open(exclusion_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_at": payload["generated_at"],
                "summary_by_classification": payload["summary_by_classification"],
                "rows": payload["exclusion_manifest"],
            },
            fh,
            indent=2,
        )

    lines = [
        "# Ambiguous Rows Report",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        f"Total ambiguous: {len(payload['ambiguous_rows'])}",
        "",
        "These rows were **not** auto-imported into the owner candidate.",
        "",
        "| table | id | reason | evidence |",
        "|---|---:|---|---|",
    ]
    for row in payload["ambiguous_rows"]:
        ev = "; ".join(row.get("evidence") or [])
        lines.append(f"| {row['table']} | {row['record_id']} | {row['reason']} | {ev[:120]} |")
    with open(ambiguous_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(json.dumps({"summary": payload["summary_by_classification"], "total": payload["total_rows"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
