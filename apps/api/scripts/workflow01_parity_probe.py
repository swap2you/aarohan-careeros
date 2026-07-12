#!/usr/bin/env python3
"""Workflow Lock 01 parity + stale-state diagnostic (READ-ONLY).

Traces the exact delta between:
  - canonical persisted owner-eligible jobs (eligible_for_owner = true)
  - production Fresh Jobs default list filter (what the owner actually sees)
  - audit dry-run recompute (evaluate_eligibility at a fixed evaluation timestamp)

Prints a JSON diagnostic to stdout. Never writes.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import text

from datetime import timedelta

from app.database import SessionLocal
from app.models import Job, WorkflowState
from app.services.discovery_policy import freshness_max_age_hours
from app.services.provenance import OWNER_EXCLUDED
from app.services.job_eligibility import (
    DECISION_ACCEPT,
    evaluate_owner_decision,
)
from scripts.audit_fresh_jobs import _job_payload, run_audit


REJECTED = WorkflowState.REJECTED.value
CLOSED = WorkflowState.CLOSED.value
PROTECTED_STATES = {
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
}


def _fixed_now(arg: str | None) -> datetime:
    if arg:
        return datetime.fromisoformat(arg.replace("Z", "")).replace(tzinfo=None)
    return datetime.utcnow()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", default=None, help="Fixed evaluation timestamp (ISO). Default: utcnow().")
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args(argv)
    now = _fixed_now(args.now)

    db = SessionLocal()
    try:
        jobs = db.query(Job).filter(~Job.data_provenance.in_(OWNER_EXCLUDED)).all()

        persisted_eligible = [j for j in jobs if j.eligible_for_owner]
        persisted_eligible_ids = sorted(j.id for j in persisted_eligible)

        # Production Fresh Jobs default filter, reproduced exactly from routers/jobs.py
        # (post-fix): owner visibility is governed by eligibility (eligible_for_owner +
        # ingest_decision) + not archived/expired + freshness, NOT by lifecycle `state`.
        age_cutoff = now - timedelta(hours=freshness_max_age_hours())
        eligible_but_hidden = []
        production_visible_ids = []
        for j in persisted_eligible:
            hidden_reasons = []
            if j.is_archived:
                hidden_reasons.append("is_archived")
            if getattr(j, "is_expired", False):
                hidden_reasons.append("is_expired")
            if not (j.ingest_decision == DECISION_ACCEPT or j.ingest_decision is None):
                hidden_reasons.append(f"ingest_decision={j.ingest_decision}")
            fresh_ok = j.state in PROTECTED_STATES or (
                j.effective_freshness_at is not None and j.effective_freshness_at >= age_cutoff
            )
            if not fresh_ok:
                hidden_reasons.append("aged_out")
            if hidden_reasons:
                eligible_but_hidden.append(
                    {
                        "id": j.id,
                        "title": j.title,
                        "state": j.state,
                        "ingest_decision": j.ingest_decision,
                        "eligible_for_owner": j.eligible_for_owner,
                        "is_archived": j.is_archived,
                        "hidden_reasons": hidden_reasons,
                    }
                )
            else:
                production_visible_ids.append(j.id)

        # Audit recompute at the SAME fixed evaluation timestamp.
        report = run_audit(db, execute=False, now=now)
        audit_accept = report["by_corrected_decision"].get(DECISION_ACCEPT, 0)
        audit_proposed_fresh = report["proposed_fresh_jobs_count"]

        # Per-job recompute at fixed now to find decision deltas vs persisted eligibility.
        recompute_accept_ids = []
        decision_delta = []
        for j in jobs:
            res = evaluate_owner_decision(_job_payload(j), now=now)
            if res.decision == DECISION_ACCEPT:
                recompute_accept_ids.append(j.id)
            persisted = bool(j.eligible_for_owner)
            recomputed = res.decision == DECISION_ACCEPT
            if persisted != recomputed:
                decision_delta.append(
                    {
                        "id": j.id,
                        "title": j.title,
                        "company": j.company,
                        "persisted_eligible": persisted,
                        "persisted_state": j.state,
                        "persisted_ingest_decision": j.ingest_decision,
                        "recomputed_decision": res.decision,
                        "recomputed_tier": res.freshness_tier,
                        "recomputed_owner_visible": res.owner_visible,
                        "reason_codes": res.reason_codes,
                    }
                )

        # State distribution of the persisted-eligible jobs.
        eligible_state_dist = {}
        for j in persisted_eligible:
            eligible_state_dist[j.state] = eligible_state_dist.get(j.state, 0) + 1

        out = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evaluation_now": now.isoformat(),
            "total_owner_jobs": len(jobs),
            "canonical_persisted_eligible_count": len(persisted_eligible),
            "canonical_persisted_eligible_ids": persisted_eligible_ids,
            "eligible_state_distribution": eligible_state_dist,
            "production_visible_count": len(production_visible_ids),
            "production_visible_ids": sorted(production_visible_ids),
            "production_eligible_but_hidden_count": len(eligible_but_hidden),
            "production_eligible_but_hidden": eligible_but_hidden,
            "audit_by_corrected_decision_ACCEPT": audit_accept,
            "audit_proposed_fresh_jobs_count": audit_proposed_fresh,
            "recompute_accept_count": len(recompute_accept_ids),
            "recompute_accept_ids": sorted(recompute_accept_ids),
            "decision_delta_persisted_vs_recomputed": decision_delta,
        }
        payload = json.dumps(out, indent=2, default=str)
        print(payload)
        if args.output_json:
            with open(args.output_json, "w", encoding="utf-8") as fh:
                fh.write(payload)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
