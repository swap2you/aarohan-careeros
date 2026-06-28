"""Plain-English application timeline events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ApplicationTimelineEvent


def record_timeline_event(
    db: Session,
    *,
    application_id: int,
    job_id: int | None,
    event_type: str,
    title: str,
    description: str | None = None,
    actor_email: str | None = None,
    metadata: dict | None = None,
) -> ApplicationTimelineEvent:
    row = ApplicationTimelineEvent(
        application_id=application_id,
        job_id=job_id,
        event_type=event_type,
        title=title,
        description=description,
        actor_email=actor_email,
        event_metadata=metadata or {},
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


TIMELINE_LABELS = {
    "discovered": "Job discovered",
    "shortlisted": "Job shortlisted",
    "packet_generated": "Application packet generated",
    "validation_completed": "Document validation completed",
    "approved": "Packet approved for submission",
    "rejected": "Packet rejected",
    "application_opened": "Official application opened",
    "submitted": "Marked as submitted by user",
    "not_submitted": "Marked as not submitted",
    "saved_for_later": "Saved for later",
    "withdrawn": "Application withdrawn",
    "duplicate_override": "Duplicate risk override recorded",
    "representation_override": "Vendor representation override recorded",
    "version_created": "New document version created",
}
