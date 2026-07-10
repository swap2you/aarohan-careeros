#!/usr/bin/env python3
"""Strengthened owner candidate validation for Phase 3 rework."""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker

from app.models import (
    Application,
    ApplicationDocumentVersion,
    AuditLog,
    Company,
    Job,
    OAuthToken,
    ProcessedGmailMessage,
    RecruiterSignal,
    User,
)
from app.services.gmail_replay import classify_processed_row, should_replay_row
from app.services.provenance import OWNER_EXCLUDED, PROVENANCE_VALIDATION
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity

E2E_EMAIL = "e2e@test.local"


def _load_json(path: str | None) -> dict | None:
    if not path or not os.path.isfile(path):
        return None
    return json.loads(open(path, encoding="utf-8").read())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3 rework candidate validation")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--oauth-json")
    parser.add_argument("--drive-json")
    parser.add_argument("--gmail-replay-json")
    parser.add_argument("--jobs-json")
    parser.add_argument("--audit-json")
    parser.add_argument("--workflow-smoke-json")
    parser.add_argument("--api-base", default=os.environ.get("CANDIDATE_API_BASE", "http://127.0.0.1:8002"))
    args = parser.parse_args(argv)

    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    defects: list[dict] = []
    checks: dict = {}

    oauth_report = _load_json(args.oauth_json)
    drive_report = _load_json(args.drive_json)
    gmail_report = _load_json(args.gmail_replay_json)
    jobs_report = _load_json(args.jobs_json)
    audit_report = _load_json(args.audit_json)
    smoke_report = _load_json(args.workflow_smoke_json)

    try:
        admin = db.query(User).filter(User.is_admin.is_(True)).count()
        checks["admin_users"] = admin
        if admin != 1:
            defects.append({"severity": "critical", "check": "single_admin_user", "detail": str(admin)})

        checks["jobs"] = db.query(Job).filter(Job.data_provenance != PROVENANCE_VALIDATION).count()
        checks["applications"] = db.query(Application).filter(
            Application.data_provenance != PROVENANCE_VALIDATION
        ).count()

        fixture_rows = db.query(Job).filter(Job.data_provenance.in_(OWNER_EXCLUDED)).count()
        if fixture_rows:
            defects.append({"severity": "high", "check": "no_fixture_jobs", "detail": str(fixture_rows)})

        e2e_users = db.query(User).filter(func.lower(User.email) == E2E_EMAIL).count()
        if e2e_users:
            defects.append({"severity": "critical", "check": "no_e2e_users", "detail": str(e2e_users)})

        if oauth_report:
            checks["oauth_passed"] = oauth_report.get("passed")
            checks["oauth_decryptable"] = oauth_report.get("decryptable_owner_tokens", 0)
            checks["oauth_requires_reconnect"] = oauth_report.get("requires_owner_reconnect", False)
            if not oauth_report.get("passed"):
                if oauth_report.get("requires_owner_reconnect"):
                    defects.append({
                        "severity": "high",
                        "check": "oauth_refresh_requires_owner_reconnect",
                        "detail": "Tokens decrypt but lack valid refresh_token — owner must reconnect Google on candidate runtime before cutover",
                    })
                else:
                    defects.append({"severity": "critical", "check": "oauth_operational", "detail": "oauth validation failed"})
        else:
            defects.append({"severity": "high", "check": "oauth_report_missing", "detail": "no OAUTH-CANDIDATE-VALIDATION.json"})

        if drive_report:
            checks["drive_blocking"] = drive_report.get("blocking")
            if drive_report.get("blocking"):
                defects.append({"severity": "high", "check": "drive_root_blocking", "detail": drive_report.get("reason")})
        else:
            defects.append({"severity": "high", "check": "drive_report_missing", "detail": "no DRIVE-ROOT-RESOLUTION.json"})

        if gmail_report:
            replay_required = gmail_report.get("summary", {}).get("REPLAY_REQUIRED_JOB_ALERT", 0)
            checks["gmail_replay_pending"] = replay_required
        else:
            defects.append({"severity": "medium", "check": "gmail_replay_report_missing", "detail": ""})

        suppressors = 0
        for row in db.query(ProcessedGmailMessage).all():
            if should_replay_row(row, db)[0]:
                continue
            if row.message_type == "JOB_ALERT" and row.produced_entity_count == 0:
                jobs_for_msg = (
                    db.query(Job)
                    .filter(text("raw_payload->>'gmail_message_id' = :mid"))
                    .params(mid=row.message_id)
                    .count()
                )
                if jobs_for_msg == 0:
                    suppressors += 1
        checks["gmail_suppressors_without_jobs"] = suppressors
        if suppressors:
            defects.append({
                "severity": "critical",
                "check": "no_gmail_suppressors",
                "detail": str(suppressors),
            })

        if jobs_report:
            counts = jobs_report.get("counts", {})
            checks["fresh_jobs_accepted"] = counts.get("accepted", 0)
            checks["fresh_jobs_owner_review"] = counts.get("owner_review", 0)
            if counts.get("accepted", 0) + counts.get("owner_review", 0) == 0:
                if jobs_report.get("blocker"):
                    defects.append({
                        "severity": "critical",
                        "check": "fresh_jobs_corpus",
                        "detail": jobs_report.get("blocker"),
                    })
        else:
            defects.append({"severity": "critical", "check": "jobs_report_missing", "detail": ""})

        if audit_report:
            checks["audit_orphan_count"] = audit_report.get("orphan_count_after")
            if audit_report.get("orphan_count_after", 1) != 0:
                defects.append({
                    "severity": "high",
                    "check": "audit_recruiter_integrity",
                    "detail": str(audit_report.get("orphan_count_after")),
                })
        else:
            defects.append({"severity": "high", "check": "audit_report_missing", "detail": ""})

        orphan_companies = (
            db.query(Company)
            .outerjoin(Job, Job.company_id == Company.id)
            .filter(Job.id.is_(None))
            .count()
        )
        if orphan_companies:
            defects.append({"severity": "medium", "check": "orphan_companies", "detail": str(orphan_companies)})

        if smoke_report:
            checks["workflow_smoke_passed"] = smoke_report.get("passed")
            if not smoke_report.get("passed"):
                defects.append({"severity": "critical", "check": "workflow_smoke", "detail": "smoke failed"})
        else:
            defects.append({"severity": "critical", "check": "workflow_smoke_missing", "detail": ""})

        try:
            health = httpx.get(f"{args.api_base.rstrip('/')}/health", timeout=10.0)
            checks["api_health"] = health.status_code == 200
            if health.status_code != 200:
                defects.append({"severity": "critical", "check": "api_health", "detail": str(health.status_code)})
        except Exception as exc:
            checks["api_health"] = False
            defects.append({"severity": "critical", "check": "api_health", "detail": str(exc)})

        marker = db.execute(
            text("SELECT purpose, identity_uuid FROM aarohan_meta.database_identity ORDER BY id LIMIT 1")
        ).one()
        checks["identity_marker"] = {"purpose": marker.purpose, "identity_uuid": str(marker.identity_uuid)}
        if marker.purpose != "OWNER_CANDIDATE":
            defects.append({"severity": "critical", "check": "identity_purpose", "detail": marker.purpose})

        validation_remaining = db.query(Application).filter(
            Application.data_provenance == PROVENANCE_VALIDATION
        ).count()
        checks["validation_provenance_remaining"] = validation_remaining
        if validation_remaining:
            defects.append({"severity": "high", "check": "no_validation_smoke_rows", "detail": str(validation_remaining)})

    finally:
        db.close()
        engine.dispose()

    result = {
        "checks": checks,
        "defects": defects,
        "passed": not defects,
        "defect_count_by_severity": {
            "critical": sum(1 for d in defects if d["severity"] == "critical"),
            "high": sum(1 for d in defects if d["severity"] == "high"),
            "medium": sum(1 for d in defects if d["severity"] == "medium"),
            "low": sum(1 for d in defects if d["severity"] == "low"),
        },
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(json.dumps({"passed": result["passed"], "defects": len(defects)}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
