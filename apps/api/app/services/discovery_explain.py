"""Per-job source & policy explainability (Workflow 01.5, Section 9).

Builds the data behind the job-detail "Why am I seeing this?" panel and makes exclusion
reasons discoverable in diagnostics without surfacing excluded rows in the Fresh Jobs list.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Job
from app.services.discovery_origin import ensure_origin


def _policy_version_label(db: Session) -> str:
    try:
        from app.services.discovery_policy_service import get_active_version

        active = get_active_version(db)
        if active:
            return f"v{active.version}" + (f" ({active.preset})" if active.preset else "")
    except Exception:
        pass
    return "defaults"


def _timestamp_confidence(job: Job) -> str:
    source = (job.freshness_source or "").lower()
    if source in {"provider_posted_at", "posted_at"}:
        return "HIGH"
    if source in {"source_received_at", "connector_fetched_at"}:
        return "MEDIUM"
    if source == "discovered_at":
        return "LOW"
    return "UNKNOWN"


def build_job_explanation(db: Session, job: Job, *, now: datetime | None = None) -> dict:
    """Return an explainability payload for a single job (owner-safe, no secrets)."""
    now = now or datetime.utcnow()
    origin = ensure_origin(job)

    source_message = None
    raw = job.raw_payload or {}
    if isinstance(raw, dict):
        gmail_id = raw.get("gmail_message_id")
        if gmail_id:
            # Redacted reference only — never expose the message body.
            source_message = f"gmail:{str(gmail_id)[:8]}…"

    # Fresh single-row recompute for reason codes / tier (does not mutate the row).
    reason_codes = list(job.ingest_reason_codes or [])
    tier = job.freshness_bucket
    try:
        from app.services.job_eligibility import evaluate_owner_decision

        payload = {
            "source": job.source,
            "external_id": job.external_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description_text": job.description_text,
            "description_html": job.description_html,
            "url": job.url,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "provider_posted_at": job.provider_posted_at,
            "source_received_at": job.source_received_at,
            "discovered_at": job.discovered_at,
            "workplace_type": job.workplace_type,
            "persisted_ingest_decision": job.ingest_decision,
            "persisted_reason_codes": job.ingest_reason_codes,
        }
        result = evaluate_owner_decision(payload, now=now)
        if result.reason_codes:
            reason_codes = result.reason_codes
        tier = result.freshness_tier or tier
    except Exception:
        pass

    return {
        "job_id": job.id,
        "origin": origin,
        "origin_detail": job.origin_detail,
        "source_provider": job.source,
        "source_message": source_message,
        "policy_version": _policy_version_label(db),
        "decision": job.ingest_decision,
        "eligible_for_owner": job.eligible_for_owner,
        "reason_codes": reason_codes,
        "freshness": {
            "tier": tier,
            "source": job.freshness_source,
            "effective_at": job.effective_freshness_at.isoformat() if job.effective_freshness_at else None,
            "timestamp_confidence": _timestamp_confidence(job),
        },
        "location_decision": {
            "eligibility": job.location_eligibility,
            "reason": job.location_eligibility_reason,
        },
        "role_profile_match": {
            "recommended_profile": job.recommended_profile,
            "role_eligibility": job.role_eligibility,
            "matched_title_patterns": job.matched_title_patterns or [],
        },
        "duplicate_disposition": {
            "canonical_url": job.canonical_url,
            "is_duplicate": (job.ingest_decision == "DUPLICATE"),
            "duplicate_reason_codes": [c for c in reason_codes if "DUPLICATE" in str(c)],
        },
        "manual": {
            "is_manual": origin == "OWNER_ADDED" or bool(job.manual_status),
            "added_by": job.added_by,
            "added_at": job.added_at.isoformat() if job.added_at else None,
            "manual_status": job.manual_status,
            "manual_protected": job.manual_protected,
        },
        "lifecycle_state": job.state,
    }
