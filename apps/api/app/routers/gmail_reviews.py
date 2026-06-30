"""Gmail ingest review queue API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import GmailIngestReview, User
from app.services.audit import write_audit
from app.services.ingestion import ingest_job

router = APIRouter(prefix="/gmail/reviews", tags=["gmail-reviews"])


class ReviewCorrectRequest(BaseModel):
    title: str | None = None
    company: str | None = None
    url: str | None = None
    location: str | None = None


def _serialize_review(row: GmailIngestReview) -> dict:
    return {
        "id": row.id,
        "status": row.status,
        "gmail_label": row.gmail_label,
        "sender": row.sender,
        "subject": row.subject,
        "snippet": row.snippet,
        "confidence": row.confidence,
        "ignored_reason": row.ignored_reason,
        "parsed_payload": row.parsed_payload,
        "job_id": row.job_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "reviewed_by": row.reviewed_by,
    }


@router.get("")
def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    query = db.query(GmailIngestReview).order_by(GmailIngestReview.created_at.desc())
    if status:
        query = query.filter(GmailIngestReview.status == status)
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_serialize_review(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


def _ingest_from_review(
    db: Session,
    row: GmailIngestReview,
    *,
    actor: str,
    overrides: dict | None = None,
):
    payload = dict(row.parsed_payload or {})
    if overrides:
        payload.update({k: v for k, v in overrides.items() if v})
    if not payload.get("title") or not payload.get("company"):
        raise HTTPException(status_code=409, detail="Review item has no parseable job payload")
    ingest_payload = {
        "source": payload.get("source", "gmail_alert"),
        "external_id": payload.get("external_id") or f"gmail-review-{row.id}",
        "title": payload["title"],
        "company": payload["company"],
        "location": payload.get("location"),
        "url": payload.get("url") or f"https://mail.google.com/review/{row.id}",
        "description_text": payload.get("description_text") or payload.get("snippet") or row.snippet or "",
        "description_html": payload.get("description_html") or "",
        "data_provenance": "gmail",
    }
    job = ingest_job(db, ingest_payload, actor=actor)
    row.job_id = job.id
    return job


@router.post("/{review_id}/approve")
def approve_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = db.query(GmailIngestReview).filter(GmailIngestReview.id == review_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Review item not found")
    if row.status == "approved":
        return _serialize_review(row)
    if not row.job_id:
        _ingest_from_review(db, row, actor=current_user.email)
    row.status = "approved"
    row.reviewed_by = current_user.email
    row.reviewed_at = datetime.utcnow()
    write_audit(
        db,
        event_type="gmail.review_approved",
        actor=current_user.email,
        resource_type="gmail_review",
        resource_id=str(review_id),
        details={"job_id": row.job_id},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_review(row)


@router.post("/{review_id}/correct")
def correct_review(
    review_id: int,
    payload: ReviewCorrectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = db.query(GmailIngestReview).filter(GmailIngestReview.id == review_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Review item not found")
    parsed = dict(row.parsed_payload or {})
    for field in ("title", "company", "url", "location"):
        val = getattr(payload, field)
        if val:
            parsed[field] = val
    row.parsed_payload = parsed
    job = _ingest_from_review(
        db,
        row,
        actor=current_user.email,
        overrides=parsed,
    )
    row.status = "approved"
    row.reviewed_by = current_user.email
    row.reviewed_at = datetime.utcnow()
    write_audit(
        db,
        event_type="gmail.review_corrected",
        actor=current_user.email,
        resource_type="gmail_review",
        resource_id=str(review_id),
        details={"job_id": job.id, "corrections": payload.model_dump(exclude_none=True)},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_review(row)


@router.post("/{review_id}/reject")
def reject_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = db.query(GmailIngestReview).filter(GmailIngestReview.id == review_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Review item not found")
    row.status = "rejected"
    row.reviewed_by = current_user.email
    row.reviewed_at = datetime.utcnow()
    write_audit(
        db,
        event_type="gmail.review_rejected",
        actor=current_user.email,
        resource_type="gmail_review",
        resource_id=str(review_id),
    )
    db.add(row)
    db.commit()
    return _serialize_review(row)
