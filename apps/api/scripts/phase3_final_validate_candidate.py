#!/usr/bin/env python3
"""Final candidate validation — must pass with zero Critical/High defects."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker

from app.models import Application, Job, ProcessedGmailMessage, User
from app.services.gmail_replay import should_replay_row
from app.services.provenance import OWNER_EXCLUDED, PROVENANCE_VALIDATION
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity

E2E_EMAIL = "e2e@test.local"


def _load(path: str | None) -> dict | None:
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Final candidate validation")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json")
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--defect-register-md", required=True)
    parser.add_argument("--oauth-json")
    parser.add_argument("--drive-json")
    parser.add_argument("--discovery-json")
    parser.add_argument("--manual-review-json")
    parser.add_argument("--backup-verification-json")
    parser.add_argument("--cutover-rehearsal-json")
    parser.add_argument("--workflow-smoke-json")
    parser.add_argument("--api-base", default="http://127.0.0.1:8002")
    args = parser.parse_args(argv)

    if not args.database_url:
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    defects: list[dict] = []
    checks: dict = {}

    oauth = _load(args.oauth_json)
    drive = _load(args.drive_json)
    discovery = _load(args.discovery_json)
    manual = _load(args.manual_review_json)
    backup = _load(args.backup_verification_json)
    cutover = _load(args.cutover_rehearsal_json)
    smoke = _load(args.workflow_smoke_json)

    try:
        if db.query(User).filter(User.is_admin.is_(True)).count() != 1:
            defects.append({"severity": "critical", "check": "single_admin_user", "detail": "admin count != 1"})
        if db.query(User).filter(func.lower(User.email) == E2E_EMAIL).count():
            defects.append({"severity": "critical", "check": "no_e2e_users", "detail": "e2e user present"})

        checks["jobs"] = db.query(Job).filter(Job.data_provenance != PROVENANCE_VALIDATION).count()
        checks["accepted_jobs"] = db.query(Job).filter(Job.eligible_for_owner.is_(True)).count()
        checks["applications"] = db.query(Application).filter(Application.data_provenance != PROVENANCE_VALIDATION).count()

        if oauth and not oauth.get("passed"):
            defects.append({"severity": "high", "check": "oauth_operational", "detail": "OAuth final validation failed"})
        elif not oauth:
            defects.append({"severity": "high", "check": "oauth_report_missing", "detail": ""})
        else:
            checks["oauth_refreshable"] = oauth.get("refreshable")
            checks["gmail_health"] = oauth.get("gmail_health")
            checks["drive_health"] = oauth.get("drive_health")

        if drive and drive.get("blocking"):
            defects.append({"severity": "high", "check": "drive_root_blocking", "detail": drive.get("reason")})
        elif not drive:
            defects.append({"severity": "high", "check": "drive_report_missing", "detail": ""})
        else:
            checks["drive_resolved"] = not drive.get("blocking")

        if discovery:
            checks["gmail_scanned"] = discovery.get("gmail_messages_scanned", 0)
            if discovery.get("gmail_messages_scanned", 0) <= 0:
                defects.append({"severity": "high", "check": "gmail_scanned", "detail": "zero messages scanned"})
            if discovery.get("gmail_suppressors_without_jobs", 0):
                defects.append({"severity": "critical", "check": "gmail_suppressors", "detail": str(discovery["gmail_suppressors_without_jobs"])})
        else:
            defects.append({"severity": "high", "check": "discovery_report_missing", "detail": ""})

        if manual and not manual.get("passed"):
            defects.append({"severity": "high", "check": "manual_job_review", "detail": "accepted jobs failed manual review"})
        elif not manual:
            defects.append({"severity": "high", "check": "manual_review_missing", "detail": ""})
        else:
            checks["manual_accepted"] = manual.get("counts", {}).get("accepted", 0)

        if backup and not backup.get("passed"):
            defects.append({"severity": "high", "check": "backup_restore_verification", "detail": "restore verification failed"})
        elif not backup:
            defects.append({"severity": "high", "check": "backup_verification_missing", "detail": ""})

        if cutover and not cutover.get("passed"):
            defects.append({"severity": "high", "check": "cutover_rehearsal", "detail": "final cutover rehearsal failed"})
        elif not cutover:
            defects.append({"severity": "high", "check": "cutover_rehearsal_missing", "detail": ""})

        if smoke and not smoke.get("passed"):
            defects.append({"severity": "critical", "check": "workflow_smoke", "detail": "smoke failed"})
        elif not smoke:
            defects.append({"severity": "critical", "check": "workflow_smoke_missing", "detail": ""})

        suppressors = 0
        for row in db.query(ProcessedGmailMessage).all():
            if should_replay_row(row, db)[0]:
                continue
            if row.message_type == "JOB_ALERT" and (row.produced_entity_count or 0) == 0:
                cnt = db.execute(
                    text("SELECT count(*) FROM jobs WHERE raw_payload->>'gmail_message_id' = :mid"),
                    {"mid": row.message_id},
                ).scalar()
                if not cnt:
                    suppressors += 1
        if suppressors:
            defects.append({"severity": "critical", "check": "gmail_suppressors", "detail": str(suppressors)})

        if db.query(Job).filter(Job.data_provenance.in_(OWNER_EXCLUDED)).count():
            defects.append({"severity": "high", "check": "no_fixture_jobs", "detail": "fixture rows present"})

        if db.query(Application).filter(Application.data_provenance == PROVENANCE_VALIDATION).count():
            defects.append({"severity": "high", "check": "validation_rows_remain", "detail": "validation provenance apps remain"})

        try:
            health = httpx.get(f"{args.api_base.rstrip('/')}/health", timeout=10.0)
            checks["api_health"] = health.status_code == 200
            if health.status_code != 200:
                defects.append({"severity": "critical", "check": "api_health", "detail": str(health.status_code)})
        except Exception as exc:
            defects.append({"severity": "critical", "check": "api_health", "detail": str(exc)})

        marker = db.execute(text("SELECT purpose, identity_uuid FROM aarohan_meta.database_identity LIMIT 1")).one()
        checks["identity"] = {"purpose": marker.purpose, "identity_uuid": str(marker.identity_uuid)}
        if marker.purpose != "OWNER_CANDIDATE":
            defects.append({"severity": "critical", "check": "identity_purpose", "detail": marker.purpose})
    finally:
        db.close()
        engine.dispose()

    by_severity = {
        "critical": sum(1 for d in defects if d["severity"] == "critical"),
        "high": sum(1 for d in defects if d["severity"] == "high"),
        "medium": sum(1 for d in defects if d["severity"] == "medium"),
        "low": sum(1 for d in defects if d["severity"] == "low"),
    }
    passed = not defects
    result = {"checks": checks, "defects": defects, "passed": passed, "defect_count_by_severity": by_severity}

    if args.output_json:
        os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)

    report = [
        "# Owner Candidate Validation Report",
        "",
        f"- **Passed:** {passed}",
        f"- **Defects:** {len(defects)}",
        "",
        "## Checks",
        "",
        f"```json\n{json.dumps(checks, indent=2)}\n```",
    ]
    Path(args.report_md).write_text("\n".join(report) + "\n", encoding="utf-8")

    reg = ["# Owner Candidate Defect Register", ""]
    if defects:
        for d in defects:
            reg.append(f"- **{d['severity'].upper()}** `{d['check']}`: {d.get('detail', '')}")
    else:
        reg.append("- No defects")
    Path(args.defect_register_md).write_text("\n".join(reg) + "\n", encoding="utf-8")

    print(json.dumps({"passed": passed, "defects": len(defects)}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
