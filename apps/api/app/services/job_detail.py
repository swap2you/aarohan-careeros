"""Assemble job detail payload for the UI."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Application, Job
from app.services.ats_detection import detect_ats
from app.services.duplicate_risk import evaluate_duplicate_risk
from app.services.representation import evaluate_representation_risk


def _safe_list(value: list | None) -> list:
    return value if isinstance(value, list) else []


def _job_age_days(posted_at: datetime | None, discovered_at: datetime | None) -> int | None:
    ref = posted_at or discovered_at
    if not ref:
        return None
    return max(0, int((datetime.utcnow() - ref).total_seconds() // 86400))


def build_job_detail(db: Session, job: Job) -> dict:
    dup = evaluate_duplicate_risk(db, job)
    rep = evaluate_representation_risk(db, job)
    ats = detect_ats(job.url or "")

    application = db.query(Application).filter(Application.job_id == job.id).one_or_none()
    app_summary = None
    if application:
        meta = application.packet_metadata or {}
        app_summary = {
            "id": application.id,
            "state": application.state,
            "updated_at": application.updated_at.isoformat() if application.updated_at else None,
            "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
            "validation_passed": (meta.get("document_quality") or {}).get("passed"),
            "drive_links": meta.get("drive_links"),
            "latest_version": (meta.get("document_version") or {}).get("version_number"),
        }

    score = job.score
    score_block = None
    if score:
        score_block = {
            "total_score": score.total_score,
            "trust_score": score.trust_score,
            "fit_reasons": _safe_list(score.fit_reasons),
            "trust_reasons": _safe_list(score.trust_reasons),
            "hard_filter_passed": score.hard_filter_passed,
            "hard_filter_reasons": _safe_list(score.hard_filter_reasons),
            "match_card": score.match_card,
            "recommendation": score.recommendation,
        }

    description = job.description_text or ""
    if not description.strip() and job.description_html:
        from app.services.sanitize import html_to_text

        description = html_to_text(job.description_html)

    return {
        "job": {
            "id": job.id,
            "title": job.title or "Untitled role",
            "company": job.company or "Unknown company",
            "location": job.location,
            "workplace_type": job.workplace_type,
            "state": job.state,
            "source": job.source,
            "url": job.url,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            "discovered_at": job.discovered_at.isoformat() if job.discovered_at else None,
            "age_days": _job_age_days(job.posted_at, job.discovered_at),
            "role_family": job.role_family,
            "is_expired": job.is_expired,
            "source_verified": job.source_verified,
            "data_provenance": getattr(job, "data_provenance", "live"),
            "description_text": description,
            "description_html": job.description_html or "",
        },
        "score": score_block,
        "duplicate_risk": dup.to_dict(),
        "representation_risk": rep.to_dict(),
        "apply_readiness": {
            "can_open_apply": dup.level.value != "RED" and rep.level.value != "RED",
            "message": "Aarohan has not submitted anything. Open the official employer URL only.",
            "official_url": job.url,
        },
        "ats": ats.to_dict(),
        "application": app_summary,
    }
