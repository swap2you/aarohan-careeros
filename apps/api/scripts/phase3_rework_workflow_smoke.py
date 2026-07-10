#!/usr/bin/env python3
"""Candidate-only workflow smoke test with validation provenance cleanup."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Application,
    ApplicationDocumentVersion,
    ApplicationEvent,
    ApplicationLedger,
    ApplicationTimelineEvent,
    ApprovalAction,
    DuplicateOverride,
    Job,
    WorkflowState,
)
from app.services.provenance import PROVENANCE_VALIDATION
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity


def _purge_validation_application(db: Session, app_id: int, job_id: int | None = None) -> None:
    ledger_ids = [
        row[0]
        for row in db.query(ApplicationLedger.id)
        .filter(ApplicationLedger.application_id == app_id)
        .all()
    ]
    if ledger_ids:
        db.query(ApplicationEvent).filter(ApplicationEvent.ledger_id.in_(ledger_ids)).delete(
            synchronize_session=False
        )
        db.query(ApplicationLedger).filter(ApplicationLedger.id.in_(ledger_ids)).delete(synchronize_session=False)
    db.query(ApprovalAction).filter(ApprovalAction.application_id == app_id).delete(synchronize_session=False)
    db.query(ApplicationTimelineEvent).filter(ApplicationTimelineEvent.application_id == app_id).delete(
        synchronize_session=False
    )
    db.query(ApplicationDocumentVersion).filter(ApplicationDocumentVersion.application_id == app_id).delete(
        synchronize_session=False
    )
    db.query(Application).filter(Application.id == app_id).delete(synchronize_session=False)
    if job_id:
        db.query(DuplicateOverride).filter(DuplicateOverride.job_id == job_id).delete(synchronize_session=False)
        job_row = db.query(Job).filter(Job.id == job_id).one_or_none()
        if job_row and job_row.data_provenance != PROVENANCE_VALIDATION:
            if job_row.eligible_for_owner:
                job_row.state = WorkflowState.SHORTLISTED.value
            else:
                job_row.state = WorkflowState.INGESTED.value
            db.add(job_row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Candidate workflow smoke test")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--api-base", default=os.environ.get("CANDIDATE_API_BASE", "http://127.0.0.1:8002"))
    parser.add_argument("--admin-email", default=os.environ.get("ADMIN_EMAIL", ""))
    parser.add_argument("--admin-password", default=os.environ.get("ADMIN_PASSWORD", ""))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--cleanup", action="store_true", default=True)
    args = parser.parse_args(argv)

    if not args.database_url or not args.admin_email or not args.admin_password:
        print("DATABASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD required", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    steps: list[dict] = []
    smoke_ids: dict = {}
    passed = False
    job: Job | None = None

    try:
        stale_apps = db.query(Application).filter(Application.data_provenance == PROVENANCE_VALIDATION).all()
        for stale in stale_apps:
            _purge_validation_application(db, stale.id, stale.job_id)
        if stale_apps:
            db.commit()
            steps.append({"step": "pre_cleanup_validation_apps", "ok": True, "removed": len(stale_apps)})

        job = (
            db.query(Job)
            .filter(Job.data_provenance != PROVENANCE_VALIDATION)
            .filter(Job.eligible_for_owner.is_(True))
            .order_by(Job.id.desc())
            .first()
        )
        if not job:
            job = (
                db.query(Job)
                .filter(Job.data_provenance != PROVENANCE_VALIDATION)
                .order_by(Job.id.desc())
                .first()
            )
        if not job:
            steps.append({"step": "select_job", "ok": False, "detail": "no candidate job available"})
            raise RuntimeError("no candidate job available")

        steps.append({"step": "select_job", "ok": True, "job_id": job.id})
        job_state_before = job.state

        with httpx.Client(base_url=args.api_base, timeout=120.0) as client:
            login = client.post(
                "/api/auth/login",
                json={"email": args.admin_email, "password": args.admin_password, "remember_me": False},
            )
            steps.append({"step": "login", "ok": login.status_code == 200, "status": login.status_code})
            if login.status_code != 200:
                raise RuntimeError(f"login failed: {login.text[:200]}")

            token = login.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}"} if token else {}

            detail = client.get(f"/api/jobs/{job.id}/detail", headers=headers)
            steps.append({"step": "job_detail", "ok": detail.status_code == 200})

            rescore = client.post(f"/api/jobs/{job.id}/rescore", headers=headers)
            steps.append({"step": "rescore_shortlist_path", "ok": rescore.status_code == 200})

            gen = client.post(
                f"/api/applications/jobs/{job.id}/generate",
                headers=headers,
                params={"resume_profile": "qe_leadership"},
            )
            gen_detail = gen.text[:300] if gen.status_code not in {200, 201} else None
            steps.append({
                "step": "generate_packet",
                "ok": gen.status_code in {200, 201},
                "status": gen.status_code,
                "detail": gen_detail,
            })
            app_id = gen.json().get("id") if gen.status_code in {200, 201} else None
            if not app_id:
                raise RuntimeError(f"generate_packet failed: {gen_detail}")

            smoke_ids["application_id"] = app_id
            app_row = db.query(Application).filter(Application.id == app_id).one()
            app_row.data_provenance = PROVENANCE_VALIDATION
            db.add(app_row)
            db.commit()

            versions = client.get(f"/api/applications/{app_id}/versions", headers=headers)
            version_items = versions.json() if versions.status_code == 200 else []
            steps.append({
                "step": "document_versions",
                "ok": versions.status_code == 200 and len(version_items) >= 1,
                "count": len(version_items),
            })

            approve = client.post(
                f"/api/applications/{app_id}/actions",
                headers=headers,
                json={"action": "approve", "notes": "phase3 validation smoke"},
            )
            steps.append({
                "step": "approval",
                "ok": approve.status_code in {200, 201},
                "status": approve.status_code,
                "detail": approve.text[:200] if approve.status_code not in {200, 201} else None,
            })

            opened = client.post(
                f"/api/applications/{app_id}/actions",
                headers=headers,
                json={"action": "opened_application", "notes": "phase3 validation smoke manual open"},
            )
            steps.append({
                "step": "manual_application_open",
                "ok": opened.status_code in {200, 201},
                "status": opened.status_code,
            })

            readiness = client.get(f"/api/applications/jobs/{job.id}/apply-readiness", headers=headers)
            readiness_body = readiness.json() if readiness.status_code == 200 else {}
            steps.append({
                "step": "apply_readiness",
                "ok": readiness.status_code == 200 and readiness_body.get("can_open_apply") is True,
                "can_open_apply": readiness_body.get("can_open_apply"),
            })

            dup = client.get(f"/api/jobs/{job.id}/detail", headers=headers)
            dup_body = dup.json() if dup.status_code == 200 else {}
            steps.append({
                "step": "duplicate_risk_visible",
                "ok": dup.status_code == 200 and "duplicate_risk" in dup_body,
            })

            timeline = client.get(f"/api/applications/{app_id}/timeline", headers=headers)
            timeline_items = timeline.json() if timeline.status_code == 200 else []
            steps.append({
                "step": "timeline",
                "ok": timeline.status_code == 200 and len(timeline_items) >= 1,
                "count": len(timeline_items),
            })

            db.refresh(app_row)
            steps.append({
                "step": "manual_application_state",
                "ok": app_row.state == WorkflowState.APPROVED_FOR_SUBMISSION.value,
                "state": app_row.state,
            })

        passed = all(s.get("ok") for s in steps)

        if args.cleanup and smoke_ids.get("application_id"):
            _purge_validation_application(db, smoke_ids["application_id"], job.id if job else None)
            db.commit()
            remaining = db.query(Application).filter(Application.data_provenance == PROVENANCE_VALIDATION).count()
            steps.append({"step": "cleanup_validation_records", "ok": remaining == 0, "remaining": remaining})
            passed = passed and remaining == 0
            if job:
                job_after = db.query(Job).filter(Job.id == job.id).one_or_none()
                steps.append({
                    "step": "job_state_restored",
                    "ok": job_after is not None and job_after.state != WorkflowState.PACKET_READY.value,
                    "state": job_after.state if job_after else None,
                    "before": job_state_before,
                })
                passed = passed and job_after is not None and job_after.state != WorkflowState.PACKET_READY.value
    except Exception as exc:
        steps.append({"step": "fatal_error", "ok": False, "detail": str(exc)[:300]})
        passed = False
    finally:
        db.close()
        engine.dispose()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": args.api_base,
        "data_provenance": PROVENANCE_VALIDATION,
        "steps": steps,
        "passed": passed,
        "smoke_ids": smoke_ids,
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"passed": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
