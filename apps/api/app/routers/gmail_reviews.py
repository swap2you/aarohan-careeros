"""Gmail ingest review queue API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import GmailIngestReview, User

router = APIRouter(prefix="/gmail/reviews", tags=["gmail-reviews"])


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
        "items": [
            {
                "id": row.id,
                "status": row.status,
                "gmail_label": row.gmail_label,
                "sender": row.sender,
                "subject": row.subject,
                "snippet": row.snippet,
                "confidence": row.confidence,
                "ignored_reason": row.ignored_reason,
                "job_id": row.job_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


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
    from datetime import datetime

    row.reviewed_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return {"id": row.id, "status": row.status}
