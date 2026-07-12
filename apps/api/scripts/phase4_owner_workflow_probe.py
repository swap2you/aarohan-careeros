#!/usr/bin/env python3
"""Phase 4 owner application functional validation against the live canonical stack.

Authenticates as the owner via local-admin-login and exercises every workflow area
listed in the final validation plan. Uses a single validation-only job (provenance=
"validation", excluded from all owner views) for the write flows and removes it
afterward, then proves zero validation-provenance rows remain.

Never sends email, never submits an application, never fabricates historical data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import httpx
from sqlalchemy import text

from app.database import SessionLocal
from app.models import Application, Job, WorkflowState
from app.services.provenance import PROVENANCE_VALIDATION

BASE = os.environ.get("OWNER_API_BASE", "http://localhost:8000")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_validation_job(db) -> int:
    # A per-run unique token keeps title/company/url distinct so duplicate-risk and
    # representation-risk cannot fire RED against a prior run's residual validation job.
    token = _now().strftime("%Y%m%d%H%M%S%f")
    job = Job(
        source="validation_probe",
        external_id=f"phase4-val-{token}",
        title=f"Senior Manager, Quality Engineering (Phase4 Validation {token})",
        company=f"Phase4 Validation Co {token}",
        location="Remote — United States",
        url=f"https://example.com/validation/phase4-qe-manager-{token}",
        description_html="<p>Validation-only record. Software quality engineering, test automation, CI/CD.</p>",
        description_text=(
            "Validation-only record. Lead software quality engineering, test automation, "
            "and CI/CD across cloud platform teams."
        ),
        posted_at=_now().replace(tzinfo=None),
        discovered_at=_now().replace(tzinfo=None),
        state=WorkflowState.SECONDARY_REVIEW.value,
        eligible_for_owner=False,
        data_provenance=PROVENANCE_VALIDATION,
        ingest_decision="validation",
        dedupe_key=f"phase4-validation-{token}",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


def _cleanup_validation(db) -> dict:
    val_job_ids = [r[0] for r in db.execute(
        text("SELECT id FROM jobs WHERE data_provenance = :p"), {"p": PROVENANCE_VALIDATION}
    ).all()]
    app_ids = []
    if val_job_ids:
        app_ids = [r[0] for r in db.execute(
            text("SELECT id FROM applications WHERE job_id = ANY(:ids)"), {"ids": val_job_ids}
        ).all()]
    if app_ids:
        # application_events reference application_ledger (ledger_id), not applications directly.
        db.execute(
            text(
                "DELETE FROM application_events WHERE ledger_id IN "
                "(SELECT id FROM application_ledger WHERE application_id = ANY(:ids))"
            ),
            {"ids": app_ids},
        )
        # recruiter_signals may reference an application; detach rather than delete signals.
        db.execute(
            text("UPDATE recruiter_signals SET application_id = NULL WHERE application_id = ANY(:ids)"),
            {"ids": app_ids},
        )
        for tbl in (
            "approval_actions",
            "application_document_versions",
            "application_timeline_events",
            "application_ledger",
        ):
            db.execute(text(f"DELETE FROM {tbl} WHERE application_id = ANY(:ids)"), {"ids": app_ids})
    if val_job_ids:
        db.execute(text("DELETE FROM applications WHERE job_id = ANY(:ids)"), {"ids": val_job_ids})
        # Detach audit rows that reference the validation job but should not be destroyed
        # by a foreign-key cascade; then clear remaining job-scoped child rows.
        db.execute(
            text("UPDATE ai_usage_records SET job_id = NULL WHERE job_id = ANY(:ids)"),
            {"ids": val_job_ids},
        )
        db.execute(
            text("UPDATE recruiter_signals SET job_id = NULL WHERE job_id = ANY(:ids)"),
            {"ids": val_job_ids},
        )
        for tbl in (
            "job_scores",
            "interview_packs",
            "duplicate_overrides",
            "representation_overrides",
            "application_timeline_events",
            "application_ledger",
            "gmail_ingest_reviews",
        ):
            db.execute(text(f"DELETE FROM {tbl} WHERE job_id = ANY(:ids)"), {"ids": val_job_ids})
        db.execute(text("DELETE FROM jobs WHERE id = ANY(:ids)"), {"ids": val_job_ids})
    db.commit()
    remaining_jobs = db.execute(
        text("SELECT count(*) FROM jobs WHERE data_provenance = :p"), {"p": PROVENANCE_VALIDATION}
    ).scalar()
    remaining_apps = db.execute(
        text("SELECT count(*) FROM applications WHERE data_provenance = :p"), {"p": PROVENANCE_VALIDATION}
    ).scalar()
    return {
        "deleted_jobs": len(val_job_ids),
        "deleted_applications": len(app_ids),
        "remaining_validation_jobs": remaining_jobs,
        "remaining_validation_applications": remaining_apps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    results: dict = {"generated_at": _now().isoformat(), "base": BASE, "areas": {}}
    client = httpx.Client(base_url=BASE, timeout=90.0, follow_redirects=False)

    def record(area: str, method: str, path: str, ok_codes=(200,), **kw):
        try:
            resp = client.request(method, path, **kw)
            ok = resp.status_code in ok_codes
            note = ""
            try:
                body = resp.json()
                if isinstance(body, dict):
                    note = ",".join(list(body.keys())[:6])
                elif isinstance(body, list):
                    note = f"list[{len(body)}]"
            except Exception:  # noqa: BLE001
                note = resp.text[:80]
            results["areas"][area] = {"method": method, "path": path, "status": resp.status_code, "ok": ok, "shape": note}
            return resp
        except Exception as exc:  # noqa: BLE001
            results["areas"][area] = {"method": method, "path": path, "status": None, "ok": False, "error": str(exc)[:160]}
            return None

    # 1. Owner login
    record("owner_login", "POST", "/api/auth/local-admin-login", json={"remember_me": True})
    # 2. Session
    sess = record("session", "GET", "/api/auth/session")
    if sess is not None:
        try:
            results["authenticated"] = bool(sess.json().get("authenticated"))
        except Exception:  # noqa: BLE001
            results["authenticated"] = False

    # Pick a real accepted job for read flows.
    db = SessionLocal()
    accepted_id = db.execute(
        text(
            "SELECT id FROM jobs WHERE eligible_for_owner = true AND data_provenance <> :p ORDER BY id LIMIT 1"
        ),
        {"p": PROVENANCE_VALIDATION},
    ).scalar()

    # 3-13 read areas (ops + ask routers are mounted at /api with no sub-prefix).
    record("overview", "GET", "/api/analytics")
    record("fresh_jobs", "GET", "/api/jobs", params={"page": 1, "page_size": 5})
    if accepted_id:
        record("job_detail", "GET", f"/api/jobs/{accepted_id}/detail")
        record("duplicate_risk", "GET", f"/api/companies/jobs/{accepted_id}/duplicate-risk")
        # interviews GET returns 404 when no prep has been generated yet — that is a valid state.
        record("interviews", "GET", f"/api/interviews/{accepted_id}", ok_codes=(200, 404))
    record("new_opportunity_extract", "POST", "/api/opportunities/extract",
           json={"plain_text": "Senior Manager, Quality Engineering — Remote US. Lead test automation and CI/CD."})
    record("new_opportunity_recommend", "POST", "/api/opportunities/recommend-profiles",
           json={"title": "Senior Manager, Quality Engineering", "description_text": "test automation, CI/CD, software quality"})
    record("gmail_review", "GET", "/api/gmail/reviews")
    record("recruiter_signals", "GET", "/api/recruiter-signals")
    record("ask_aarohan", "POST", "/api/ask", json={"question": "How many jobs are currently shortlisted?"})
    record("settings", "GET", "/api/integrations/status")

    # Write cycle on a validation-only job. Packet generation runs BEFORE rescore so
    # the shortlist scoring cannot move the job to a state that blocks generation.
    write_cycle: dict = {}
    vjob_id = _create_validation_job(db)
    write_cycle["validation_job_id"] = vjob_id
    record("manual_application_readiness", "GET", f"/api/applications/jobs/{vjob_id}/apply-readiness")
    gen = record("packet_generation", "POST", f"/api/applications/jobs/{vjob_id}/generate",
                 params={"resume_profile": "qe_leadership"}, ok_codes=(200, 201))
    app_id = None
    if gen is not None and gen.status_code in (200, 201):
        try:
            app_id = gen.json().get("id")
        except Exception:  # noqa: BLE001
            app_id = None
    if app_id:
        write_cycle["validation_application_id"] = app_id
        record("immutable_document_version", "GET", f"/api/applications/{app_id}/versions")
        record("approval", "POST", f"/api/applications/{app_id}/actions", json={"action": "approve"}, ok_codes=(200, 409))
    else:
        results["areas"]["immutable_document_version"] = {"ok": None, "note": "packet not generated (see packet_generation)"}
        results["areas"]["approval"] = {"ok": None, "note": "no application to approve (see packet_generation)"}
    # shortlist scoring path (validated last so it cannot block packet generation).
    record("shortlist", "POST", f"/api/jobs/{vjob_id}/rescore", ok_codes=(200, 201))

    # Cleanup and prove no validation rows remain.
    try:
        cleanup = _cleanup_validation(db)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        cleanup = {"error": str(exc)[:200], "remaining_validation_jobs": -1, "remaining_validation_applications": -1}
    write_cycle["cleanup"] = cleanup
    results["write_cycle"] = write_cycle
    db.close()
    client.close()

    # Every exercised area must not be an explicit failure (True or None/skipped are acceptable).
    areas_ok = all(v.get("ok") is not False for v in results["areas"].values())
    no_residue = cleanup["remaining_validation_jobs"] == 0 and cleanup["remaining_validation_applications"] == 0
    results["passed"] = bool(results.get("authenticated") and areas_ok and no_residue)
    results["no_validation_records_remain"] = no_residue

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(json.dumps({"passed": results["passed"], "authenticated": results.get("authenticated"), "no_residue": no_residue}))
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
