"""Ingest jobs through Fresh Jobs eligibility gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Job, WorkflowState
from app.services.audit import write_audit
from app.services.duplicate_risk import description_fingerprint, link_job_to_company
from app.services.gmail_alert_parsers import canonical_job_url
from app.services.job_eligibility import (
    CLOSED_POSTING,
    DECISION_ACCEPT,
    DECISION_DUPLICATE,
    DECISION_HISTORICAL,
    DECISION_OWNER_REVIEW,
    DECISION_QUARANTINE,
    DECISION_REJECT,
    DECISION_SECONDARY,
    DUPLICATE_CANONICAL_URL,
    DUPLICATE_FINGERPRINT,
    DUPLICATE_PROVIDER_ID,
    EligibilityResult,
    evaluate_eligibility,
)
from app.services.normalization import build_dedupe_key, parse_salary_range
from app.services.provenance import infer_provenance
from app.services.sanitize import html_to_text, sanitize_html
from app.services.scoring import score_job


@dataclass
class IngestOutcome:
    decision: str
    job: Job | None = None
    reason_codes: list[str] | None = None
    reasons: list[str] | None = None
    eligibility: EligibilityResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "job_id": self.job.id if self.job else None,
            "reason_codes": self.reason_codes or [],
            "reasons": self.reasons or [],
        }


def _decision_to_state(decision: str) -> str:
    if decision == DECISION_ACCEPT:
        return WorkflowState.NORMALIZED.value
    if decision in {DECISION_SECONDARY, DECISION_QUARANTINE, DECISION_OWNER_REVIEW}:
        return WorkflowState.SECONDARY_REVIEW.value
    if decision == DECISION_HISTORICAL:
        return WorkflowState.CLOSED.value
    if decision == DECISION_REJECT:
        return WorkflowState.REJECTED.value
    return WorkflowState.NORMALIZED.value


def ingest_job_with_decision(
    db: Session,
    payload: dict,
    *,
    actor: str = "system",
    skip_eligibility: bool = False,
    allow_discovered_at: bool = False,
    persist_rejects: bool = True,
) -> IngestOutcome:
    """Normalize → gate → persist. Rejects may be persisted for audit or skipped."""
    source = payload["source"]
    external_id = str(payload["external_id"])
    existing = (
        db.query(Job)
        .filter(Job.source == source, Job.external_id == external_id)
        .one_or_none()
    )
    if existing:
        return IngestOutcome(
            decision=DECISION_DUPLICATE,
            job=existing,
            reason_codes=[DUPLICATE_PROVIDER_ID],
            reasons=["Duplicate provider source + external_id"],
        )

    description_html = sanitize_html(payload.get("description_html", ""))
    description_text = payload.get("description_text") or html_to_text(description_html)
    salary_text = payload.get("salary_text") or description_text
    salary_min, salary_max = parse_salary_range(salary_text)
    if payload.get("salary_min") is not None:
        salary_min = payload["salary_min"]
    if payload.get("salary_max") is not None:
        salary_max = payload["salary_max"]

    company = payload["company"]
    title = payload["title"]
    location = payload.get("location")
    url = payload.get("url") or ""
    canonical = canonical_job_url(url) if url else url
    dedupe_key = build_dedupe_key(company, title, location)
    fingerprint = description_fingerprint(description_text or "")

    if canonical:
        url_dup = db.query(Job).filter(Job.canonical_url == canonical).one_or_none()
    else:
        url_dup = None

    duplicate = db.query(Job).filter(Job.dedupe_key == dedupe_key).one_or_none()
    if duplicate:
        write_audit(
            db,
            event_type="job.deduplicated",
            actor=actor,
            resource_type="job",
            resource_id=str(duplicate.id),
            details={"incoming_external_id": external_id, "source": source},
        )
        return IngestOutcome(
            decision=DECISION_DUPLICATE,
            job=duplicate,
            reason_codes=[DUPLICATE_FINGERPRINT],
            reasons=["Duplicate company+title+location fingerprint"],
        )

    # Same URL but different fingerprint (e.g. retitled posting): persist for duplicate-risk.
    gate_payload_url_dup = bool(url_dup)

    gate_payload = {
        **payload,
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "description_text": description_text,
        "salary_min": salary_min,
        "salary_max": salary_max,
    }
    if skip_eligibility or payload.get("data_provenance") in {"fixture", "test"}:
        eligibility = EligibilityResult(decision=DECISION_ACCEPT)
        eligibility.freshness_source = "discovered_at"
        eligibility.effective_freshness_at = datetime.utcnow()
        eligibility.freshness_bucket = "TODAY"
        eligibility.freshness_tier = "TODAY"
        eligibility.freshness_hours = 0.0
        eligibility.location_eligibility = "ELIGIBLE_US"
        eligibility.role_eligibility = "primary"
    else:
        eligibility = evaluate_eligibility(
            gate_payload,
            allow_discovered_at=allow_discovered_at or source == "user_forwarded_links",
        )

    if gate_payload_url_dup and url_dup:
        eligibility.decision = DECISION_DUPLICATE
        eligibility.reason_codes = list(dict.fromkeys([*(eligibility.reason_codes or []), DUPLICATE_CANONICAL_URL]))
        eligibility.reasons = list(
            dict.fromkeys([*(eligibility.reasons or []), f"Duplicate canonical URL of job #{url_dup.id}"])
        )

    decision = eligibility.decision
    if decision == DECISION_DUPLICATE:
        # Persist ineligible copy for ledger/duplicate-risk; do not treat as Fresh Jobs accept.
        pass
    if decision == DECISION_REJECT and not persist_rejects:
        return IngestOutcome(
            decision=decision,
            reason_codes=eligibility.reason_codes,
            reasons=eligibility.reasons,
            eligibility=eligibility,
        )

    discovered_at = datetime.utcnow()
    posted_at = eligibility.provider_posted_at
    if posted_at is None:
        raw_posted = payload.get("posted_at") or payload.get("provider_posted_at")
        if isinstance(raw_posted, str):
            try:
                posted_at = datetime.fromisoformat(raw_posted.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                posted_at = None
        elif isinstance(raw_posted, datetime):
            posted_at = raw_posted

    provenance = infer_provenance(source, explicit=payload.get("data_provenance"), payload=payload)
    owner_confirmed = bool(payload.get("owner_confirmed") or payload.get("manual_confirmed"))
    eligible_for_owner = (
        decision == DECISION_ACCEPT and provenance not in {"fixture", "test"}
    ) or (
        owner_confirmed
        and decision not in {DECISION_REJECT, DECISION_DUPLICATE}
        and provenance not in {"fixture", "test"}
    )
    if decision == DECISION_DUPLICATE:
        eligible_for_owner = False
        state = WorkflowState.SECONDARY_REVIEW.value
    else:
        state = _decision_to_state(decision)
    is_archived = decision in {DECISION_REJECT, DECISION_HISTORICAL} and (
        CLOSED_POSTING in (eligibility.reason_codes or []) or decision == DECISION_HISTORICAL
    )

    job = Job(
        source=source,
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        workplace_type=payload.get("workplace_type"),
        salary_min=salary_min,
        salary_max=salary_max,
        description_html=description_html,
        description_text=description_text or "",
        url=url,
        canonical_url=canonical or None,
        posted_at=posted_at,
        provider_posted_at=eligibility.provider_posted_at or posted_at,
        source_received_at=eligibility.source_received_at,
        effective_freshness_at=eligibility.effective_freshness_at or discovered_at,
        freshness_source=eligibility.freshness_source or "discovered_at",
        freshness_bucket=eligibility.freshness_bucket,
        freshness_hours=eligibility.freshness_hours,
        location_eligibility=eligibility.location_eligibility,
        location_eligibility_reason=eligibility.location_reason,
        role_eligibility=eligibility.role_eligibility,
        role_eligibility_reason=eligibility.role_eligibility_reason,
        recommended_profile=eligibility.recommended_profile,
        profile_scores=eligibility.profile_scores or None,
        matched_title_patterns=eligibility.matched_title_patterns or None,
        ingest_decision=decision,
        ingest_reason_codes=eligibility.reason_codes or None,
        ingest_reasons=eligibility.reasons or None,
        eligible_for_owner=eligible_for_owner,
        is_archived=is_archived,
        discovered_at=discovered_at,
        dedupe_key=dedupe_key,
        state=state,
        raw_payload=payload,
        requisition_id=payload.get("requisition_id"),
        ats_job_id=payload.get("ats_job_id"),
        description_fingerprint=fingerprint,
        data_provenance=provenance,
        role_family=eligibility.recommended_profile,
        match_summary="; ".join(eligibility.reasons[:3]) if eligibility.reasons else None,
    )
    # Canonical discovery-origin classification (Workflow 01.5 §8).
    from app.services.discovery_origin import classify_origin

    job.origin = classify_origin(
        source=source,
        data_provenance=provenance,
        message_type=(payload.get("raw_payload") or {}).get("message_type") if isinstance(payload.get("raw_payload"), dict) else None,
    )
    db.add(job)
    db.flush()
    link_job_to_company(db, job)
    db.commit()
    db.refresh(job)

    # Score all persisted rows so hard-filter / trust diagnostics remain available.
    score_job(db, job)
    db.refresh(job)

    write_audit(
        db,
        event_type="job.ingested",
        actor=actor,
        resource_type="job",
        resource_id=str(job.id),
        details={
            "source": source,
            "company": company,
            "title": title,
            "decision": decision,
            "reason_codes": eligibility.reason_codes,
            "eligible_for_owner": eligible_for_owner,
        },
    )
    return IngestOutcome(
        decision=decision,
        job=job,
        reason_codes=eligibility.reason_codes,
        reasons=eligibility.reasons,
        eligibility=eligibility,
    )


def ingest_job(
    db: Session,
    payload: dict,
    *,
    actor: str = "system",
    allow_discovered_at: bool = False,
) -> Job:
    """Backward-compatible ingest used by existing callers.

    Fixture/test provenance skips Fresh Jobs gates so controlled tests still work.
    Rejected live jobs are still persisted with REJECTED state for audit/remediation.
    """
    provenance = payload.get("data_provenance")
    skip = provenance in {"fixture", "test"}
    outcome = ingest_job_with_decision(
        db,
        payload,
        actor=actor,
        skip_eligibility=skip,
        allow_discovered_at=allow_discovered_at
        or payload.get("source") in {"user_forwarded_links", "manual_opportunity"}
        or bool(payload.get("owner_confirmed")),
        persist_rejects=True,
    )
    if outcome.job is None:
        # Should not happen with persist_rejects=True; create a minimal rejected stub path
        raise RuntimeError(f"Ingest produced no job: {outcome.decision} {outcome.reason_codes}")
    return outcome.job
