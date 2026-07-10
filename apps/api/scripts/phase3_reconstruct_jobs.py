#!/usr/bin/env python3
"""Reconstruct Fresh Jobs corpus for owner candidate using current eligibility gates."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Job
from app.services.job_eligibility import (
    DECISION_ACCEPT,
    DECISION_OWNER_REVIEW,
    DECISION_QUARANTINE,
    DECISION_REJECT,
    DECISION_SECONDARY,
    evaluate_eligibility,
)
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity
from app.services.recovery_row_classification import CLASS_LIVE_RECONSTRUCT, CLASS_OWNER_CONFIRMED


def _job_payload(job: Job) -> dict:
    return {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "description_text": job.description_text,
        "description_html": job.description_html,
        "source": job.source,
        "external_id": job.external_id,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "provider_posted_at": job.provider_posted_at.isoformat() if job.provider_posted_at else None,
        "source_received_at": job.source_received_at.isoformat() if job.source_received_at else None,
        "discovered_at": job.discovered_at.isoformat() if job.discovered_at else None,
        "state": job.state,
        "raw_payload": job.raw_payload or {},
        "requisition_id": job.requisition_id,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3 Fresh Jobs reconstruction")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--classification-json", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    classification = json.loads(open(args.classification_json, encoding="utf-8").read())
    allowed_job_ids = {
        row["record_id"]
        for row in classification.get("rows", [])
        if row["table"] == "jobs"
        and row["classification"] in {CLASS_LIVE_RECONSTRUCT, CLASS_OWNER_CONFIRMED}
    }

    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    now = datetime.utcnow()
    accepted: list[dict] = []
    owner_review: list[dict] = []
    quarantined: list[dict] = []
    rejected: list[dict] = []
    imported_ids: list[int] = []

    try:
        for job in db.query(Job).filter(Job.id.in_(allowed_job_ids)).order_by(Job.id):
            payload = _job_payload(job)
            result = evaluate_eligibility(payload, now=now)
            entry = {
                "job_id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source": job.source,
                "url": job.url,
                "decision": result.decision,
                "reason_codes": result.reason_codes,
                "reasons": result.reasons,
                "freshness_bucket": result.freshness_bucket,
                "location_eligibility": result.location_eligibility,
            }
            if result.decision == DECISION_ACCEPT:
                accepted.append(entry)
                imported_ids.append(job.id)
            elif result.decision in {DECISION_OWNER_REVIEW, DECISION_SECONDARY}:
                owner_review.append(entry)
                imported_ids.append(job.id)
            elif result.decision == DECISION_QUARANTINE:
                quarantined.append(entry)
            else:
                rejected.append(entry)
    finally:
        db.close()
        engine.dispose()

    report = {
        "generated_at": now.isoformat() + "Z",
        "evaluated_jobs": len(allowed_job_ids),
        "import_job_ids": imported_ids,
        "counts": {
            "accepted": len(accepted),
            "owner_review": len(owner_review),
            "quarantined": len(quarantined),
            "rejected": len(rejected),
        },
        "samples": {
            "accepted": accepted[:5],
            "owner_review": owner_review[:5],
            "quarantined": quarantined[:5],
            "rejected": rejected[:5],
        },
        "all_results": {
            "accepted": accepted,
            "owner_review": owner_review,
            "quarantined": quarantined,
            "rejected": rejected,
        },
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"counts": report["counts"], "import_job_ids": len(imported_ids)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
