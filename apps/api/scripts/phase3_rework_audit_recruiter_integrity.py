#!/usr/bin/env python3
"""Clean orphan audit/recruiter records on candidate database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Application, AuditLog, Job, RecruiterSignal, User
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity

E2E_EMAIL = "e2e@test.local"
FIXTURE_ACTORS = {"e2e@test.local", "pg@test.local", "fixture", "playwright"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit/recruiter integrity cleanup")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--apply", action="store_true", help="Delete excluded/sanitized rows")
    args = parser.parse_args(argv)

    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    job_ids = {row.id for row in db.query(Job.id).all()}
    app_ids = {row.id for row in db.query(Application.id).all()}
    owner_emails = {
        (row.email or "").lower()
        for row in db.query(User).filter(User.is_admin.is_(True)).all()
    }

    excluded_groups: dict[str, list[int]] = defaultdict(list)
    sanitized_groups: dict[str, list[int]] = defaultdict(list)
    retained_audit = 0
    retained_signals = 0

    try:
        for row in db.query(AuditLog).order_by(AuditLog.id).all():
            actor = (row.actor or "").lower()
            if actor in FIXTURE_ACTORS or actor == E2E_EMAIL:
                excluded_groups["fixture_actor"].append(row.id)
                continue
            rt = (row.resource_type or "").lower()
            rid = row.resource_id
            if rt in {"job", "jobs"} and rid:
                try:
                    if int(rid) not in job_ids:
                        excluded_groups["orphan_job_reference"].append(row.id)
                        continue
                except ValueError:
                    pass
            if rt in {"application", "applications"} and rid:
                try:
                    if int(rid) not in app_ids:
                        excluded_groups["orphan_application_reference"].append(row.id)
                        continue
                except ValueError:
                    pass
            if row.event_type in {"job.ingested", "job.deduplicated"} and not job_ids:
                excluded_groups["job_event_without_jobs"].append(row.id)
                continue
            retained_audit += 1

        for row in db.query(RecruiterSignal).order_by(RecruiterSignal.id).all():
            if (row.gmail_message_id or "").startswith("fixture-"):
                excluded_groups["fixture_gmail_signal"].append(row.id)
                continue
            if row.source == "gmail_fixture":
                excluded_groups["fixture_source"].append(row.id)
                continue
            if row.job_id and row.job_id not in job_ids:
                excluded_groups["orphan_signal_job"].append(row.id)
                continue
            if row.application_id and row.application_id not in app_ids:
                excluded_groups["orphan_signal_application"].append(row.id)
                continue
            retained_signals += 1

        if args.apply:
            audit_group_keys = {
                "fixture_actor",
                "orphan_job_reference",
                "orphan_application_reference",
                "job_event_without_jobs",
            }
            signal_group_keys = {
                "fixture_gmail_signal",
                "fixture_source",
                "orphan_signal_job",
                "orphan_signal_application",
            }
            audit_delete: set[int] = set()
            signal_delete: set[int] = set()
            for key, ids in excluded_groups.items():
                if key in audit_group_keys:
                    audit_delete.update(ids)
                if key in signal_group_keys:
                    signal_delete.update(ids)
            if audit_delete:
                db.query(AuditLog).filter(AuditLog.id.in_(audit_delete)).delete(synchronize_session=False)
            if signal_delete:
                db.query(RecruiterSignal).filter(RecruiterSignal.id.in_(signal_delete)).delete(
                    synchronize_session=False
                )
            db.commit()
            job_ids = {row.id for row in db.query(Job.id).all()}
            app_ids = {row.id for row in db.query(Application.id).all()}

        orphan_after = 0
        for row in db.query(AuditLog).all():
            rt = (row.resource_type or "").lower()
            rid = row.resource_id
            if rt in {"job", "jobs"} and rid:
                try:
                    if int(rid) not in job_ids:
                        orphan_after += 1
                except ValueError:
                    pass
        for row in db.query(RecruiterSignal).all():
            if row.job_id and row.job_id not in job_ids:
                orphan_after += 1
            if row.application_id and row.application_id not in app_ids:
                orphan_after += 1

        report = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "applied": args.apply,
            "retained": {"audit_logs": retained_audit, "recruiter_signals": retained_signals},
            "excluded_count": sum(len(v) for v in excluded_groups.values()),
            "sanitized_count": sum(len(v) for v in sanitized_groups.values()),
            "orphan_count_after": orphan_after,
            "excluded_groups": {k: {"count": len(v), "sample_ids": v[:10]} for k, v in excluded_groups.items()},
            "passed": orphan_after == 0,
        }
    finally:
        db.close()
        engine.dispose()

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"orphan_count_after": report["orphan_count_after"], "passed": report["passed"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
