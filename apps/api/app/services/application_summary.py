"""Serialize applications with human-readable job context for list/queue views."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Application
from app.services.document_versions import list_versions


def _validation_status(application: Application) -> str:
    meta = application.packet_metadata or {}
    quality = meta.get("document_quality") or {}
    if quality.get("passed") is True:
        return "passed"
    if quality.get("passed") is False:
        return "failed"
    return "unknown"


def _duplicate_risk(application: Application) -> str | None:
    meta = application.packet_metadata or {}
    dup = meta.get("duplicate_risk") or {}
    level = dup.get("level")
    return str(level) if level else None


def serialize_application(application: Application, *, db: Session | None = None) -> dict:
    job = application.job
    latest_version = application.latest_version_number or 0
    generated_at = None
    if db is not None:
        versions = list_versions(db, application.id)
        if versions:
            generated_at = versions[-1].created_at.isoformat()
    elif application.document_versions:
        latest = max(application.document_versions, key=lambda v: v.version_number)
        generated_at = latest.created_at.isoformat() if latest.created_at else None

    return {
        "id": application.id,
        "job_id": application.job_id,
        "state": application.state,
        "cover_letter": application.cover_letter,
        "recruiter_note": application.recruiter_note,
        "resume_docx_path": application.resume_docx_path,
        "resume_pdf_path": application.resume_pdf_path,
        "packet_metadata": application.packet_metadata,
        "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
        "updated_at": application.updated_at.isoformat() if application.updated_at else None,
        "job_title": job.title if job else None,
        "company_name": job.company if job else None,
        "official_url": job.url if job else None,
        "packet_version": f"v{latest_version:02d}" if latest_version else None,
        "validation_status": _validation_status(application),
        "duplicate_risk": _duplicate_risk(application),
        "generated_at": generated_at,
    }
