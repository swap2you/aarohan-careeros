# Fresh Jobs data audit (Workflow Lock 01)
# Dry-run by default. Optional execution archives/reclassifies — does not delete.

param(
    [switch]$Execute,
    [string]$ConfirmationText = "",
    [string]$ApiBase = "http://127.0.0.1:8000",
    [string]$ReportDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $ReportDir) {
    $ReportDir = Join-Path $RepoRoot "generated\job-discovery-audit"
}
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $ReportDir "fresh-jobs-audit-$stamp.json"

Write-Host "Aarohan Fresh Jobs audit (dry-run unless -Execute)" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

# Prefer in-process Python audit so we do not require a live API session token.
$pythonScript = @'
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

repo = Path(sys.argv[1])
report_path = Path(sys.argv[2])
execute = sys.argv[3] == "1"
confirm = sys.argv[4] if len(sys.argv) > 4 else ""

sys.path.insert(0, str(repo / "apps" / "api"))
from app.database import SessionLocal
from app.models import Job, WorkflowState
from app.services.job_eligibility import evaluate_eligibility
from app.services.discovery_policy import freshness_max_age_hours
from app.services.provenance import OWNER_EXCLUDED

db = SessionLocal()
try:
    jobs = db.query(Job).filter(~Job.data_provenance.in_(OWNER_EXCLUDED)).all()
    now = datetime.utcnow()
    max_age = freshness_max_age_hours()
    by_source = Counter()
    by_age = Counter()
    by_geo = Counter()
    by_role = Counter()
    by_state = Counter()
    missing_ts = []
    malformed_gmail = []
    gitlab_board = []
    duplicates = []
    propose_fresh = []
    propose_archive = []
    propose_quarantine = []
    propose_reject = []

    seen_keys = {}
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
            or (job.title or "").lower() in {"linkedin job alert", "indeed job alert", "linkedin role"}
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
            "posted_at": (job.provider_posted_at or job.posted_at).isoformat() if (job.provider_posted_at or job.posted_at) else None,
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
        if result.decision == "ACCEPT" and result.freshness_hours is not None and result.freshness_hours <= max_age:
            propose_fresh.append(entry)
        elif result.decision == "QUARANTINE" or result.decision == "SECONDARY_REVIEW":
            propose_quarantine.append(entry)
        elif result.decision == "REJECT":
            if "STALE_OVER_48_HOURS" in result.reason_codes or "FOREIGN_ONLY" in result.reason_codes:
                propose_archive.append(entry)
            else:
                propose_reject.append(entry)

    report = {
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
    }

    if execute:
        if confirm != "ARCHIVE STALE AND INELIGIBLE JOBS":
            report["execute_error"] = "ConfirmationText mismatch; no changes applied"
        else:
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

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "report_path": str(report_path),
        "total_owner_jobs": report["total_owner_jobs"],
        "proposed_fresh_jobs_count": report["proposed_fresh_jobs_count"],
        "proposed_archive_count": report["proposed_archive_count"],
        "proposed_quarantine_count": report["proposed_quarantine_count"],
        "proposed_reject_count": report["proposed_reject_count"],
    }, indent=2))
finally:
    db.close()
'@

$tmpPy = Join-Path $env:TEMP "aarohan-fresh-jobs-audit.py"
Set-Content -Path $tmpPy -Value $pythonScript -Encoding UTF8

$execFlag = if ($Execute) { "1" } else { "0" }
python $tmpPy $RepoRoot.Path $reportPath $execFlag $ConfirmationText
if ($LASTEXITCODE -ne 0) {
    throw "Audit script failed with exit code $LASTEXITCODE"
}
Write-Host "Report written: $reportPath" -ForegroundColor Green
Write-Host "Dry-run only by default. To apply archive/reclassify:" -ForegroundColor Yellow
Write-Host '  pwsh .\scripts\local\Audit-FreshJobsData.ps1 -Execute -ConfirmationText "ARCHIVE STALE AND INELIGIBLE JOBS"'
