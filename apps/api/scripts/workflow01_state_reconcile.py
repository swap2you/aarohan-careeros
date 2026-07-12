#!/usr/bin/env python3
"""Workflow Lock 01 — bounded, gated owner-eligibility lifecycle-state reconciliation.

Aligns the lifecycle `state` field with canonical eligibility for owner-eligible jobs that
still carry a stale terminal state (REJECTED/CLOSED) left behind by legacy fit/trust
scoring. Eligibility (eligible_for_owner + ingest_decision) is NOT changed — only the
lifecycle field is advanced to NORMALIZED. No rows are deleted or archived.

Dry-run by default. Execute requires the exact confirmation phrase and runs in a single
transaction with count/decision validation and rollback on any unexpected result.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

CONFIRMATION_PHRASE = "APPROVE WORKFLOW 01 ELIGIBILITY STATE RECONCILIATION"
TARGET_STATE = "NORMALIZED"


def _assert_owner_identity(db: Session) -> None:
    from app.services.owner_database_identity_preflight import (
        OWNER_DATABASE,
        expected_owner_identity_purpose,
        expected_owner_identity_uuid,
        validate_owner_database_marker,
    )

    if db.get_bind().dialect.name != "postgresql":
        return
    validate_owner_database_marker(
        db.get_bind(),
        expected_purpose=expected_owner_identity_purpose(),
        expected_uuid=expected_owner_identity_uuid(),
        expected_database=OWNER_DATABASE,
    )


def _targets(db: Session):
    from app.models import Job, WorkflowState
    from app.services.provenance import OWNER_EXCLUDED

    stale_terminal = [WorkflowState.REJECTED.value, WorkflowState.CLOSED.value]
    protected = [
        WorkflowState.SHORTLISTED.value,
        WorkflowState.PACKET_READY.value,
        WorkflowState.PACKET_GENERATING.value,
        WorkflowState.NEEDS_EDIT.value,
        WorkflowState.APPROVED_FOR_SUBMISSION.value,
        WorkflowState.SUBMITTED.value,
        WorkflowState.FOLLOW_UP_DUE.value,
        WorkflowState.RECRUITER_SIGNAL.value,
        WorkflowState.INTERVIEW_SIGNAL.value,
        WorkflowState.INTERVIEW_SCHEDULED.value,
        WorkflowState.OFFER.value,
    ]
    return (
        db.query(Job)
        .filter(
            ~Job.data_provenance.in_(OWNER_EXCLUDED),
            Job.eligible_for_owner.is_(True),
            Job.ingest_decision == "ACCEPT",
            Job.state.in_(stale_terminal),
            ~Job.state.in_(protected),
        )
        .order_by(Job.id)
        .all()
    )


def run(db: Session, *, execute: bool = False, confirmation_text: str = "") -> dict:
    from app.models import Job
    from app.services.provenance import OWNER_EXCLUDED

    _assert_owner_identity(db)

    if not execute:
        from sqlalchemy import text

        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))

    rows = _targets(db)
    manifest = [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "eligible_for_owner": j.eligible_for_owner,
            "ingest_decision": j.ingest_decision,
            "before_state": j.state,
            "after_state": TARGET_STATE,
        }
        for j in rows
    ]
    eligible_before = (
        db.query(Job)
        .filter(~Job.data_provenance.in_(OWNER_EXCLUDED), Job.eligible_for_owner.is_(True))
        .count()
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "execute" if execute else "dry_run",
        "confirmation_phrase_required": CONFIRMATION_PHRASE,
        "target_state": TARGET_STATE,
        "target_row_count": len(rows),
        "target_ids": [j.id for j in rows],
        "targets": manifest,
        "canonical_eligible_before": eligible_before,
        "records_updated": 0,
    }

    if not execute:
        return report

    if confirmation_text != CONFIRMATION_PHRASE:
        report["mode"] = "execute_blocked"
        report["execute_error"] = "ConfirmationText mismatch; no changes applied"
        return report

    from app.services.owner_database_identity_preflight import (
        expected_owner_identity_uuid,
        sql_revalidate_owner_identity_marker,
    )
    from sqlalchemy import text

    if db.get_bind().dialect.name == "postgresql":
        db.execute(text(sql_revalidate_owner_identity_marker(expected_owner_identity_uuid())))

    expected_ids = {j.id for j in rows}
    changed = 0
    for j in rows:
        # Eligibility must NOT change — only advance the lifecycle field.
        assert j.eligible_for_owner is True and j.ingest_decision == "ACCEPT"
        j.state = TARGET_STATE
        changed += 1

    # SessionLocal is configured with autoflush=False, so the pending state changes must be
    # flushed to the open transaction before the validation re-query reads them; otherwise the
    # re-query returns the pre-change (committed) rows and the run rolls back spuriously.
    db.flush()

    # Validate before commit; roll back on any unexpected count or decision drift.
    still_stale = _targets(db)
    eligible_after = (
        db.query(Job)
        .filter(~Job.data_provenance.in_(OWNER_EXCLUDED), Job.eligible_for_owner.is_(True))
        .count()
    )
    ok = (
        changed == len(expected_ids)
        and len(still_stale) == 0
        and eligible_after == eligible_before
    )
    if not ok:
        db.rollback()
        report["mode"] = "rolled_back"
        report["execute_error"] = (
            f"Unexpected result (changed={changed}, remaining_stale={len(still_stale)}, "
            f"eligible_before={eligible_before}, eligible_after={eligible_after})"
        )
        return report

    db.commit()
    report["records_updated"] = changed
    report["canonical_eligible_after"] = eligible_after
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow Lock 01 lifecycle-state reconciliation")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation-text", default="")
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args(argv)

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        report = run(db, execute=args.execute, confirmation_text=args.confirmation_text)
    finally:
        db.close()
    payload = json.dumps(report, indent=2, default=str)
    print(payload)
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as fh:
            fh.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
