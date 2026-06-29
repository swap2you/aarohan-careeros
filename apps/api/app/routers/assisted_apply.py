from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Application, Job, User
from app.services.assisted_apply import (
    prepare_assisted_apply,
    record_assisted_open,
    reject_assisted_submit,
)
from app.services.ats_detection import detect_ats

router = APIRouter(prefix="/assisted-apply", tags=["assisted-apply"])


class AssistedOpenRequest(BaseModel):
    notes: str | None = None


@router.get("/jobs/{job_id}/ats-detection")
def job_ats_detection(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return detect_ats(job.url).to_dict()


@router.post("/applications/{application_id}/prepare")
def assisted_prepare(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    application = db.query(Application).filter(Application.id == application_id).one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        return prepare_assisted_apply(db, application, actor=current_user.email).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/applications/{application_id}/open")
def assisted_open(
    application_id: int,
    payload: AssistedOpenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    application = db.query(Application).filter(Application.id == application_id).one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    prepared = prepare_assisted_apply(db, application, actor=current_user.email)
    if not prepared.can_proceed:
        raise HTTPException(status_code=409, detail=prepared.blocked_reason or "Assisted apply blocked")
    record_assisted_open(db, application, actor=current_user.email, notes=payload.notes)
    return {
        "status": "opened",
        "official_url": prepared.official_url,
        "message": prepared.stop_before_submit_message,
        "mode": "ASSISTED",
    }


@router.post("/applications/{application_id}/attempt-submit")
def assisted_attempt_submit(
    application_id: int,
    _: User = Depends(get_current_user),
) -> dict:
    try:
        reject_assisted_submit()
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    raise HTTPException(status_code=403, detail="Submit not allowed")
