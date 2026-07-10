#!/usr/bin/env python3
"""Final live discovery: Gmail replay + connectors with full evidence fields."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, text
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
    TIER_HISTORICAL,
    evaluate_eligibility,
    evaluate_freshness,
)
from app.services.provenance import PROVENANCE_VALIDATION
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity


def _job_row(job: Job, result, now) -> dict:
    payload = {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "description_text": job.description_text,
        "source": job.source,
        "posted_at": job.posted_at,
        "source_received_at": job.source_received_at,
        "discovered_at": job.discovered_at,
    }
    tier, ts_source, _, age_hours, _, _, _, _ = evaluate_freshness(payload, now=now)
    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "official_url": job.url,
        "source": job.source,
        "timestamp_source": ts_source or job.freshness_source,
        "age_hours": age_hours,
        "freshness_tier": tier or job.freshness_bucket,
        "role_profile": job.recommended_profile or result.recommended_profile,
        "decision": result.decision,
        "reason_codes": result.reason_codes,
        "reasons": result.reasons,
        "eligible_for_owner": job.eligible_for_owner,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Final candidate live discovery")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--gmail-max", type=int, default=200)
    args = parser.parse_args(argv)

    if not args.database_url:
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    now = datetime.utcnow()
    report: dict = {
        "generated_at": now.isoformat(),
        "gmail_messages_scanned": 0,
        "gmail_messages_replayed": 0,
        "connector_sources_attempted": [],
        "sources_skipped": [],
        "source_errors": [],
        "extracted_jobs": 0,
        "accepted": [],
        "owner_review": [],
        "quarantined": [],
        "rejected": [],
        "duplicates": [],
    }

    try:
        backfill_legacy_rows(db)
        replay_eligible = sum(1 for row in db.query(ProcessedGmailMessage).all() if should_replay_row(row, db)[0])
        report["gmail_replay_eligible"] = replay_eligible

        try:
            messages = fetch_aarohan_labeled_messages(db, max_results=args.gmail_max)
            report["gmail_messages_scanned"] = len(messages)
            sync_result = sync_messages(db, messages, actor="phase3_final")
            report["gmail_sync"] = sync_result
            report["gmail_messages_replayed"] = sync_result.get("processed", 0)
        except Exception as exc:
            report["source_errors"].append({"source": "gmail", "error": str(exc)[:240]})

        try:
            discovery = discover_fresh_jobs(db, actor="phase3_final")
            report["discovery"] = discovery
            report["connector_sources_attempted"] = discovery.get("sources_attempted") or []
            report["sources_skipped"] = discovery.get("sources_skipped") or []
            if discovery.get("source_errors"):
                report["source_errors"].extend(discovery["source_errors"])
        except Exception as exc:
            report["source_errors"].append({"source": "discovery", "error": str(exc)[:240]})

        jobs = db.query(Job).filter(Job.data_provenance != PROVENANCE_VALIDATION).order_by(Job.id).all()
        report["extracted_jobs"] = len(jobs)
        for job in jobs:
            payload = {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "description_text": job.description_text,
                "source": job.source,
                "posted_at": job.posted_at,
                "source_received_at": job.source_received_at,
                "discovered_at": job.discovered_at,
            }
            result = evaluate_eligibility(payload, now=now)
            entry = _job_row(job, result, now)
            if job.eligible_for_owner and result.decision == DECISION_ACCEPT:
                report["accepted"].append(entry)
            elif result.decision in {DECISION_OWNER_REVIEW, DECISION_SECONDARY}:
                report["owner_review"].append(entry)
            elif result.decision == DECISION_QUARANTINE:
                report["quarantined"].append(entry)
            elif "DUPLICATE" in " ".join(result.reason_codes).upper():
                report["duplicates"].append(entry)
            else:
                report["rejected"].append(entry)

        suppressors = 0
        for row in db.query(ProcessedGmailMessage).all():
            if should_replay_row(row, db)[0]:
                continue
            if row.message_type == "JOB_ALERT" and (row.produced_entity_count or 0) == 0:
                jobs_for_msg = db.execute(
                    text("SELECT count(*) FROM jobs WHERE raw_payload->>'gmail_message_id' = :mid"),
                    {"mid": row.message_id},
                ).scalar()
                if not jobs_for_msg:
                    suppressors += 1
        report["gmail_suppressors_without_jobs"] = suppressors

        report["counts"] = {
            "accepted": len(report["accepted"]),
            "owner_review": len(report["owner_review"]),
            "quarantined": len(report["quarantined"]),
            "rejected": len(report["rejected"]),
            "duplicates": len(report["duplicates"]),
        }
        report["passed"] = (
            report["gmail_messages_scanned"] > 0
            and suppressors == 0
            and (report["counts"]["accepted"] + report["counts"]["owner_review"] > 0
                 or replay_eligible == 0)
        )
    finally:
        db.close()
        engine.dispose()

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"passed": report.get("passed"), "gmail_scanned": report["gmail_messages_scanned"]}))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
