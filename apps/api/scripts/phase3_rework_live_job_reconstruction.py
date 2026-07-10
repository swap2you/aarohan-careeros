#!/usr/bin/env python3
"""Live Fresh Jobs reconstruction on candidate: Gmail replay + discovery connectors."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Job, ProcessedGmailMessage
from app.services.fresh_jobs_discovery import discover_fresh_jobs
from app.services.gmail_lifecycle import sync_messages
from app.services.gmail_replay import backfill_legacy_rows, should_replay_row
from app.services.google_api import fetch_aarohan_labeled_messages
from app.services.job_eligibility import (
    DECISION_ACCEPT,
    DECISION_OWNER_REVIEW,
    DECISION_QUARANTINE,
    DECISION_REJECT,
    DECISION_SECONDARY,
    evaluate_eligibility,
)
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity


def _job_entry(job: Job, result) -> dict:
    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "source": job.source,
        "url": job.url,
        "freshness_bucket": job.freshness_bucket or result.freshness_bucket,
        "recommended_profile": job.recommended_profile,
        "decision": result.decision,
        "reason_codes": result.reason_codes,
        "reasons": result.reasons,
        "age_hours": (
            (datetime.utcnow() - job.effective_freshness_at).total_seconds() / 3600
            if job.effective_freshness_at
            else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Candidate live job reconstruction")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--gmail-max", type=int, default=100)
    parser.add_argument("--skip-gmail", action="store_true")
    parser.add_argument("--skip-discovery", action="store_true")
    args = parser.parse_args(argv)

    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    now = datetime.utcnow()
    report: dict = {
        "generated_at": now.isoformat() + "Z",
        "source_messages_scanned": 0,
        "messages_replayed": 0,
        "gmail_sync": {},
        "discovery": {},
        "jobs_extracted": 0,
        "accepted": [],
        "owner_review": [],
        "quarantined": [],
        "rejected": [],
        "duplicates": [],
        "source_errors": [],
        "skipped_sources": [],
    }

    try:
        backfill_legacy_rows(db)
        replay_ids = [
            row.message_id
            for row in db.query(ProcessedGmailMessage).all()
            if row.message_id and should_replay_row(row, db)[0]
        ]
        report["messages_eligible_replay"] = len(replay_ids)

        if not args.skip_gmail:
            try:
                messages = fetch_aarohan_labeled_messages(db, max_results=args.gmail_max)
                report["source_messages_scanned"] = len(messages)
                # Include replay-eligible already-fetched messages by re-processing
                sync_result = sync_messages(db, messages, actor="phase3_rework")
                report["gmail_sync"] = sync_result
                report["messages_replayed"] = sync_result.get("processed", 0)
            except Exception as exc:
                report["source_errors"].append({"source": "gmail", "error": str(exc)})

        if not args.skip_discovery:
            try:
                discovery = discover_fresh_jobs(db, actor="phase3_rework")
                report["discovery"] = discovery
                report["skipped_sources"] = discovery.get("skipped_sources") or []
                if discovery.get("source_errors"):
                    report["source_errors"].extend(discovery["source_errors"])
            except Exception as exc:
                report["source_errors"].append({"source": "discovery", "error": str(exc)})

        jobs = db.query(Job).filter(Job.data_provenance != "validation").order_by(Job.id).all()
        report["jobs_extracted"] = len(jobs)
        for job in jobs:
            payload = {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "description_text": job.description_text,
                "source": job.source,
                "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                "source_received_at": job.source_received_at.isoformat() if job.source_received_at else None,
            }
            result = evaluate_eligibility(payload, now=now)
            entry = _job_entry(job, result)
            if result.decision == DECISION_ACCEPT:
                report["accepted"].append(entry)
            elif result.decision in {DECISION_OWNER_REVIEW, DECISION_SECONDARY}:
                report["owner_review"].append(entry)
            elif result.decision == DECISION_QUARANTINE:
                report["quarantined"].append(entry)
            else:
                report["rejected"].append(entry)

        report["counts"] = {
            "accepted": len(report["accepted"]),
            "owner_review": len(report["owner_review"]),
            "quarantined": len(report["quarantined"]),
            "rejected": len(report["rejected"]),
        }
        report["passed"] = (
            report["counts"]["accepted"] + report["counts"]["owner_review"] > 0
            or (report["source_messages_scanned"] == 0 and not report["discovery"])
        )
        if report["counts"]["accepted"] == 0 and report["counts"]["owner_review"] == 0:
            if report["source_messages_scanned"] > 0 or report.get("discovery", {}).get("attempted"):
                report["passed"] = False
                report["blocker"] = "zero_accepted_or_owner_review_with_qualifying_sources"
    finally:
        db.close()
        engine.dispose()

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"counts": report["counts"], "passed": report.get("passed")}))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
