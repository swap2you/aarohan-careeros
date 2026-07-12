"""Canonical discovery-origin classification and manual-opportunity helpers (Workflow 01.5).

``Job.origin`` is a single canonical category (see :class:`app.models.JobOrigin`) derived from
``data_provenance`` and ``source``. It is distinct from:
- ``data_provenance`` — owner-visibility exclusion of fixture/test/validation rows,
- ``state`` — the connector application lifecycle,
- ``manual_status`` — owner-facing tracking of manually added / applied-to opportunities.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Job, JobOrigin, ManualOpportunityStatus, WorkflowState

_ATS_SOURCES = {"greenhouse", "lever", "ashby"}
_MANUAL_PROVENANCE = {"manual", "user_forwarded_links", "manual_opportunity", "ad_hoc"}


def classify_origin(*, source: str | None, data_provenance: str | None, message_type: str | None = None) -> str:
    """Deterministically classify a job row into a canonical :class:`JobOrigin` value."""
    provenance = (data_provenance or "").lower()
    src = (source or "").lower()
    if provenance in _MANUAL_PROVENANCE or src in {"ad_hoc", "manual"}:
        return JobOrigin.OWNER_ADDED.value
    if (message_type or "").upper() in {"RECRUITER", "RECRUITER_SIGNAL", "RECRUITER_MESSAGE"}:
        return JobOrigin.RECRUITER_MESSAGE.value
    if provenance == "gmail" or "gmail" in src or src.endswith("_alert_emails"):
        return JobOrigin.GMAIL_ALERT.value
    if src in _ATS_SOURCES:
        return JobOrigin.ATS_BOARD.value
    return JobOrigin.PUBLIC_CONNECTOR.value


def ensure_origin(job: Job) -> str:
    """Return the job's origin, backfilling it from provenance/source when missing."""
    if job.origin:
        return job.origin
    job.origin = classify_origin(source=job.source, data_provenance=job.data_provenance)
    return job.origin


def backfill_origins(db: Session) -> dict:
    """Backfill ``origin`` for any rows missing it (idempotent). Returns counts by origin."""
    from collections import Counter

    counts: Counter = Counter()
    for job in db.query(Job).filter(Job.origin.is_(None)).all():
        job.origin = classify_origin(source=job.source, data_provenance=job.data_provenance)
        counts[job.origin] += 1
    if counts:
        db.commit()
    return dict(counts)


def mark_owner_added(
    job: Job,
    *,
    added_by: str,
    manual_status: str = ManualOpportunityStatus.SAVED.value,
    owner_confirmed: bool = True,
) -> Job:
    """Flag a job as an owner-added, freshness-protected manual opportunity."""
    job.origin = JobOrigin.OWNER_ADDED.value
    job.data_provenance = "manual"
    job.added_by = added_by
    job.added_at = datetime.utcnow()
    job.owner_confirmed = owner_confirmed
    job.manual_protected = True
    job.manual_status = manual_status
    return job


# Manual statuses that imply the opportunity is actively tracked and must not age out.
PROTECTED_MANUAL_STATUSES = {
    ManualOpportunityStatus.SHORTLISTED.value,
    ManualOpportunityStatus.APPLIED.value,
    ManualOpportunityStatus.INTERVIEWING.value,
    ManualOpportunityStatus.OFFER.value,
}


def set_manual_status(job: Job, status: str) -> Job:
    """Set owner-facing manual tracking status and keep freshness protection consistent."""
    valid = {s.value for s in ManualOpportunityStatus}
    if status not in valid:
        raise ValueError(f"invalid manual status: {status}")
    job.manual_status = status
    if status in PROTECTED_MANUAL_STATUSES or job.origin == JobOrigin.OWNER_ADDED.value:
        job.manual_protected = True
    return job


def is_manual_opportunity(job: Job) -> bool:
    return job.origin == JobOrigin.OWNER_ADDED.value or bool(job.manual_status)


def manual_opportunity_dict(job: Job) -> dict:
    """Public representation of a manual / tracked opportunity."""
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "origin": job.origin,
        "added_by": job.added_by,
        "added_at": job.added_at.isoformat() if job.added_at else None,
        "owner_confirmed": job.owner_confirmed,
        "manual_protected": job.manual_protected,
        "manual_status": job.manual_status,
        "state": job.state,
        "eligible_for_owner": job.eligible_for_owner,
    }
