"""Fresh Jobs owner-data audit (Workflow Lock 01).

Dry-run by default. Optional execute archives/reclassifies — never deletes.
Intended to run inside the API container where DATABASE_URL is valid.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

CONFIRMATION_PHRASE = "ARCHIVE STALE AND INELIGIBLE JOBS"


def _redact_secrets(text: str) -> str:
    """Best-effort scrub of connection strings / password-like tokens from messages."""
    import re

    text = re.sub(r"postgresql\+?[^:\s]*://[^\s]+", "postgresql://***", text, flags=re.I)
    text = re.sub(r"(password|secret|token|api[_-]?key)\s*[:=]\s*\S+", r"\1=***", text, flags=re.I)
    return text


def run_audit(
    db: Session,
    *,
    execute: bool = False,
    confirmation_text: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Analyze owner jobs and optionally archive/reclassify. Never deletes rows."""
    from app.models import Job, WorkflowState
    from app.services.discovery_policy import freshness_max_age_hours
    from app.services.job_eligibility import evaluate_eligibility
    from app.services.provenance import OWNER_EXCLUDED

    now = now or datetime.utcnow()
    jobs = db.query(Job).filter(~Job.data_provenance.in_(OWNER_EXCLUDED)).all()
    max_age = freshness_max_age_hours()

    by_source: Counter = Counter()
    by_age: Counter = Counter()
    by_geo: Counter = Counter()
    by_role: Counter = Counter()
    by_state: Counter = Counter()
    missing_ts: list[int] = []
    malformed_gmail: list[dict] = []
    gitlab_board: list[dict] = []
    duplicates: list[dict] = []
    propose_fresh: list[dict] = []
    propose_archive: list[dict] = []
    propose_quarantine: list[dict] = []
    propose_reject: list[dict] = []

    seen_keys: dict[tuple[str, str], int] = {}
    for job in jobs:
        by_source[job.source] += 1
        by_state[job.state] += 1
        by_role[job.role_family or job.recommended_profile or "unknown"] += 1
        by_geo[job.location_eligibility or "unknown"] += 1

        eff = job.effective_freshness_at or job.posted_at or job.source_received_at
        if not eff:
            missing_ts.append(job.id)
            by_age["missing_timestamp"] += 1
        else:
            hours = (now - eff).total_seconds() / 3600.0
            if hours <= 24:
                by_age["0_24h"] += 1
            elif hours <= 48:
                by_age["24_48h"] += 1
            else:
                by_age["over_48h"] += 1

        if job.source in {"linkedin_alert_emails", "indeed_alert_emails"} and (
            (job.company or "").lower() in {"unknown employer", "unknown company"}
            or (job.title or "").lower()
            in {"linkedin job alert", "indeed job alert", "linkedin role"}
        ):
            malformed_gmail.append({"id": job.id, "title": job.title, "company": job.company})

        if job.source == "greenhouse_public_get" and (
            (job.company or "").lower() == "gitlab"
            or "gitlab" in (job.external_id or "").lower()
        ):
            gitlab_board.append({"id": job.id, "title": job.title, "company": job.company})

        key = (job.source, job.external_id)
        if key in seen_keys:
            duplicates.append({"id": job.id, "dup_of": seen_keys[key], "key": list(key)})
        else:
            seen_keys[key] = job.id

        payload = {
            "source": job.source,
            "external_id": job.external_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "description_text": job.description_text,
            "workplace_type": job.workplace_type,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "posted_at": (job.provider_posted_at or job.posted_at).isoformat()
            if (job.provider_posted_at or job.posted_at)
            else None,
            "source_received_at": job.source_received_at.isoformat() if job.source_received_at else None,
        }
        result = evaluate_eligibility(payload, now=now)
        entry = {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "source": job.source,
            "decision": result.decision,
            "reason_codes": result.reason_codes,
            "reasons": result.reasons,
        }
        if (
            result.decision == "ACCEPT"
            and result.freshness_hours is not None
            and result.freshness_hours <= max_age
        ):
            propose_fresh.append(entry)
        elif result.decision in {"QUARANTINE", "SECONDARY_REVIEW"}:
            propose_quarantine.append(entry)
        elif result.decision == "REJECT":
            if "STALE_OVER_48_HOURS" in result.reason_codes or "FOREIGN_ONLY" in result.reason_codes:
                propose_archive.append(entry)
            else:
                propose_reject.append(entry)

    report: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "mode": "execute" if execute else "dry_run",
        "total_owner_jobs": len(jobs),
        "by_source": dict(by_source),
        "by_age_bucket": dict(by_age),
        "by_geography_eligibility": dict(by_geo),
        "by_role_family": dict(by_role),
        "by_state": dict(by_state),
        "missing_timestamps": missing_ts,
        "malformed_gmail_jobs": malformed_gmail,
        "gitlab_hardcoded_board_jobs": gitlab_board,
        "duplicates": duplicates,
        "proposed_fresh_jobs_count": len(propose_fresh),
        "proposed_archive_count": len(propose_archive),
        "proposed_quarantine_count": len(propose_quarantine),
        "proposed_reject_count": len(propose_reject),
        "proposed_fresh_jobs": propose_fresh[:200],
        "proposed_archive": propose_archive[:500],
        "proposed_quarantine": propose_quarantine[:500],
        "proposed_reject": propose_reject[:500],
        "records_updated": 0,
    }

    if execute:
        if confirmation_text != CONFIRMATION_PHRASE:
            report["execute_error"] = "ConfirmationText mismatch; no changes applied"
            report["mode"] = "execute_blocked"
            return report

        changed = 0
        for entry in propose_archive + propose_reject:
            job = db.query(Job).filter(Job.id == entry["id"]).one_or_none()
            if not job:
                continue
            job.is_archived = True
            job.eligible_for_owner = False
            job.ingest_decision = entry["decision"]
            job.ingest_reason_codes = entry["reason_codes"]
            job.ingest_reasons = entry["reasons"]
            if entry["decision"] == "REJECT":
                job.state = WorkflowState.REJECTED.value
            else:
                job.state = WorkflowState.CLOSED.value
            changed += 1
        for entry in propose_quarantine:
            job = db.query(Job).filter(Job.id == entry["id"]).one_or_none()
            if not job:
                continue
            job.eligible_for_owner = False
            job.ingest_decision = entry["decision"]
            job.ingest_reason_codes = entry["reason_codes"]
            job.ingest_reasons = entry["reasons"]
            job.state = WorkflowState.SECONDARY_REVIEW.value
            changed += 1
        for entry in propose_fresh:
            job = db.query(Job).filter(Job.id == entry["id"]).one_or_none()
            if not job:
                continue
            job.eligible_for_owner = True
            job.is_archived = False
            job.ingest_decision = "ACCEPT"
            changed += 1
        db.commit()
        report["records_updated"] = changed

    return report


def summary_from_report(report: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "total_owner_jobs": report.get("total_owner_jobs", 0),
        "proposed_fresh_jobs_count": report.get("proposed_fresh_jobs_count", 0),
        "proposed_archive_count": report.get("proposed_archive_count", 0),
        "proposed_quarantine_count": report.get("proposed_quarantine_count", 0),
        "proposed_reject_count": report.get("proposed_reject_count", 0),
        "mode": report.get("mode"),
    }
    if report.get("mode") == "execute":
        summary["records_updated"] = report.get("records_updated", 0)
    if report.get("execute_error"):
        summary["execute_error"] = report["execute_error"]
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fresh Jobs owner-data audit")
    parser.add_argument("--execute", action="store_true", help="Apply archive/reclassify (requires confirmation)")
    parser.add_argument(
        "--confirmation-text",
        default="",
        help=f'Must equal "{CONFIRMATION_PHRASE}" when --execute is set',
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print full report JSON to stdout (no file write)",
    )
    args = parser.parse_args(argv)

    try:
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            report = run_audit(
                db,
                execute=args.execute,
                confirmation_text=args.confirmation_text,
            )
        finally:
            db.close()
    except Exception as exc:
        err = {"ok": False, "error": _redact_secrets(str(exc))}
        print(json.dumps(err), flush=True)
        return 1

    # Always emit a machine-readable envelope on stdout for the PowerShell wrapper.
    envelope = {
        "ok": True,
        "summary": summary_from_report(report),
        "report": report,
    }
    print(json.dumps(envelope), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
