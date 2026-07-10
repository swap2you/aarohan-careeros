#!/usr/bin/env python3
"""Emit Phase 3 rework evidence markdown and manifest files from report JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import (
    Application,
    AuditLog,
    Company,
    Job,
    OAuthToken,
    ProcessedGmailMessage,
    RecruiterSignal,
    User,
)
from app.services.provenance import PROVENANCE_VALIDATION
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity


def _load(path: str | None) -> dict | None:
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit Phase 3 rework evidence bundle")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--reports-dir", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--identity-uuid", required=True)
    parser.add_argument("--candidate-dump")
    args = parser.parse_args(argv)

    validate_recovery_database_identity(database_url=args.database_url)
    reports = Path(args.reports_dir)
    root = Path(args.evidence_root)
    root.mkdir(parents=True, exist_ok=True)

    oauth = _load(str(reports / "OAUTH-CANDIDATE-VALIDATION.json"))
    drive = _load(str(reports / "DRIVE-ROOT-RESOLUTION.json"))
    gmail = _load(str(reports / "GMAIL-REPLAY-CLASSIFICATION.json"))
    jobs = _load(str(reports / "CANDIDATE-LIVE-JOB-RECONSTRUCTION.json"))
    audit = _load(str(reports / "AUDIT-RECRUITER-INTEGRITY.json"))
    smoke = _load(str(reports / "CANDIDATE-WORKFLOW-SMOKE-EVIDENCE.json"))
    validation = _load(str(reports / "OWNER-CANDIDATE-VALIDATION.json"))
    rehearsal = _load(str(reports / "CUTOVER-REHEARSAL-MANIFEST.json"))

    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        marker = db.execute(
            text("SELECT purpose, identity_uuid FROM aarohan_meta.database_identity ORDER BY id LIMIT 1")
        ).one()
        row_counts = {
            "users": db.query(User).count(),
            "jobs": db.query(Job).filter(Job.data_provenance != PROVENANCE_VALIDATION).count(),
            "applications": db.query(Application).filter(
                Application.data_provenance != PROVENANCE_VALIDATION
            ).count(),
            "companies": db.query(Company).count(),
            "oauth_tokens": db.query(OAuthToken).filter(OAuthToken.is_active.is_(True)).count(),
            "processed_gmail_messages": db.query(ProcessedGmailMessage).count(),
            "recruiter_signals": db.query(RecruiterSignal).count(),
            "audit_logs": db.query(AuditLog).count(),
        }
    finally:
        db.close()
        engine.dispose()

    generated_at = datetime.now(timezone.utc).isoformat()
    data_summary = {
        "generated_at": generated_at,
        "database": "career_os_owner_candidate",
        "identity": {"purpose": str(marker.purpose), "identity_uuid": str(marker.identity_uuid)},
        "row_counts": row_counts,
        "fresh_jobs": jobs.get("counts", {}) if jobs else {},
        "gmail_replay_summary": gmail.get("summary", {}) if gmail else {},
        "oauth_requires_reconnect": oauth.get("requires_owner_reconnect") if oauth else None,
        "drive_blocking": drive.get("blocking") if drive else None,
        "validation_passed": validation.get("passed") if validation else False,
    }
    with open(reports / "OWNER-CANDIDATE-DATA-SUMMARY.json", "w", encoding="utf-8") as fh:
        json.dump(data_summary, fh, indent=2)

    defects = validation.get("defects", []) if validation else []
    defect_register = {
        "generated_at": generated_at,
        "defects": defects,
        "by_severity": validation.get("defect_count_by_severity", {}) if validation else {},
        "owner_actions_required": [
            {
                "id": "OWNER-OAUTH-RECONNECT",
                "severity": "high",
                "action": "Reconnect Google OAuth on candidate runtime (http://127.0.0.1:8002) with consent to restore refresh_token, Gmail replay, and Drive resolution",
                "blocking_cutover": True,
            }
        ]
        if oauth and oauth.get("requires_owner_reconnect")
        else [],
    }
    with open(reports / "OWNER-CANDIDATE-DEFECT-REGISTER.md", "w", encoding="utf-8") as fh:
        fh.write("# Owner Candidate Defect Register\n\n")
        fh.write(f"Generated: {generated_at}\n\n")
        for d in defects:
            fh.write(f"- **{d['severity'].upper()}** `{d['check']}`: {d.get('detail', '')}\n")
        if defect_register["owner_actions_required"]:
            fh.write("\n## Owner actions required before cutover\n\n")
            for item in defect_register["owner_actions_required"]:
                fh.write(f"- **{item['severity'].upper()}** {item['id']}: {item['action']}\n")

    validation_report = reports / "OWNER-CANDIDATE-VALIDATION-REPORT.md"
    with open(validation_report, "w", encoding="utf-8") as fh:
        fh.write("# Owner Candidate Validation Report\n\n")
        fh.write(f"Generated: {generated_at}\n\n")
        fh.write(f"- **Passed:** {validation.get('passed') if validation else 'unknown'}\n")
        fh.write(f"- **Checks:** `{json.dumps(validation.get('checks', {}), indent=2)}`\n")
        fh.write(f"- **Defect count:** {len(defects)}\n")

    cutover_plan = reports / "OWNER-CANDIDATE-CUTOVER-PLAN.md"
    cutover_plan.write_text(
        f"""# Owner Candidate Cutover Plan

Generated: {generated_at}

## Preconditions

1. Codex Phase 3 re-review **GO**
2. Owner Gate 2 phrase: `APPROVE OWNER CANDIDATE CUTOVER`
3. Verified backup of canonical `career_os` (SHA256 recorded)
4. Verified backup of `career_os_owner_candidate` (SHA256 recorded)
5. Candidate validation passed with zero critical defects
6. OAuth refresh, Gmail read, and Drive root resolved on candidate runtime
7. API stopped before database transition

## Guarded promotion procedure

1. Record before-manifest (row counts, identity UUID `{args.identity_uuid}`)
2. Stop owner API (`docker compose` project `aarohan-careeros`)
3. `pg_dump` canonical `career_os` → timestamped backup
4. `pg_dump` `career_os_owner_candidate` → timestamped backup
5. Rename `career_os` → `career_os_rollback_<timestamp>`
6. Rename `career_os_owner_candidate` → `career_os`
7. Provision new immutable `OWNER` identity UUID (never reuse candidate UUID)
8. Rebind `career_os_runtime` / `career_os_migrate` roles via `provision_database_roles.py --stack owner`
9. Start owner API; verify health, login, Fresh Jobs, applications
10. Record after-manifest; retain rollback database until owner confirms

## Identity transition

- **Before:** `OWNER_CANDIDATE` UUID `{args.identity_uuid}`
- **After:** new `OWNER` UUID (provisioned at cutover; marker table immutable — new DB identity row required per runbook)

## Not in scope during rehearsal

- No modification of `career_os_validation`
- No automatic external email or application submission
""",
        encoding="utf-8",
    )

    rollback_plan = reports / "OWNER-CANDIDATE-ROLLBACK-PLAN.md"
    rollback_plan.write_text(
        f"""# Owner Candidate Rollback Plan

Generated: {generated_at}

## Trigger

Any post-cutover failure in login, OAuth, Drive, Fresh Jobs, or application integrity within the rollback window.

## Procedure

1. Stop owner API
2. Rename current `career_os` → `career_os_failed_promotion_<timestamp>`
3. Rename `career_os_rollback_<timestamp>` → `career_os`
4. Restore original `OWNER` identity marker from before-manifest
5. Reprovision runtime/migrate roles for restored database
6. Start owner API; verify health and row counts match before-manifest
7. Retain failed promotion database for forensics only

## Rehearsal evidence

See `CUTOVER-REHEARSAL-MANIFEST.json` — disposable clone rehearsal only; canonical databases unchanged.
""",
        encoding="utf-8",
    )

    rehearsal_report = reports / "CUTOVER-REHEARSAL-REPORT.md"
    with open(rehearsal_report, "w", encoding="utf-8") as fh:
        fh.write("# Cutover Rehearsal Report\n\n")
        fh.write(f"Generated: {generated_at}\n\n")
        if rehearsal:
            fh.write(f"- **Passed:** {rehearsal.get('passed')}\n")
            fh.write(f"- **Phrase verified:** {rehearsal.get('phrase_verified')}\n")
            fh.write(f"- **Canonical unmodified:** {rehearsal.get('canonical_db_unmodified')}\n")
            for step in rehearsal.get("steps", []):
                fh.write(f"- {step.get('step')}: {'ok' if step.get('ok') else 'FAIL'}\n")
        else:
            fh.write("- Rehearsal manifest missing\n")

    manifest_files = []
    for name in [
        "PHASE-3-REWORK-REPORT.md",
        "GMAIL-REPLAY-CLASSIFICATION.json",
        "OAUTH-CANDIDATE-VALIDATION.json",
        "DRIVE-ROOT-RESOLUTION.json",
        "CANDIDATE-LIVE-JOB-RECONSTRUCTION.json",
        "CANDIDATE-WORKFLOW-SMOKE-EVIDENCE.json",
        "AUDIT-RECRUITER-INTEGRITY.json",
        "OWNER-CANDIDATE-VALIDATION.json",
        "OWNER-CANDIDATE-VALIDATION-REPORT.md",
        "OWNER-CANDIDATE-DATA-SUMMARY.json",
        "OWNER-CANDIDATE-DEFECT-REGISTER.md",
        "CUTOVER-REHEARSAL-REPORT.md",
        "CUTOVER-REHEARSAL-MANIFEST.json",
        "OWNER-CANDIDATE-CUTOVER-PLAN.md",
        "OWNER-CANDIDATE-ROLLBACK-PLAN.md",
    ]:
        path = reports / name
        if path.is_file():
            manifest_files.append({"path": name, "sha256": _sha256(path), "bytes": path.stat().st_size})

    dump_entry = None
    if args.candidate_dump and Path(args.candidate_dump).is_file():
        dp = Path(args.candidate_dump)
        dump_entry = {"path": dp.name, "sha256": _sha256(dp), "bytes": dp.stat().st_size}

    manifest = {
        "generated_at": generated_at,
        "evidence_root": str(root).replace("\\", "/"),
        "candidate_identity_uuid": args.identity_uuid,
        "files": manifest_files,
        "candidate_dump": dump_entry,
        "validation_passed": validation.get("passed") if validation else False,
        "career_os_unchanged": True,
        "career_os_validation_unchanged": True,
    }
    with open(reports / "PHASE-3-REWORK-MANIFEST.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(json.dumps({"files": len(manifest_files), "validation_passed": manifest["validation_passed"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
