#!/usr/bin/env python3
"""Classify candidate processed Gmail rows for replay recovery."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import ProcessedGmailMessage
from app.services.gmail_replay import backfill_legacy_rows, classify_processed_row
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gmail replay classification for candidate DB")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        backfill = backfill_legacy_rows(db)
        rows = db.query(ProcessedGmailMessage).order_by(ProcessedGmailMessage.id).all()
        classified = [classify_processed_row(row, db) for row in rows]
        summary = dict(Counter(item["classification"] for item in classified))
        report = {
            "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "total": len(classified),
            "summary": summary,
            "backfill": backfill,
            "rows": classified,
        }
    finally:
        db.close()
        engine.dispose()

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"total": report["total"], "summary": summary}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
