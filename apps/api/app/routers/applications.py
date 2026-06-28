from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Application, ApplicationTimelineEvent, Job, User, WorkflowState
from app.schemas import ApplicationOut, ApprovalRequest
from app.services.approval import apply_approval_action
from app.services.document_versions import list_versions
from app.services.documents import generate_application_packet
from app.services.duplicate_risk import evaluate_duplicate_risk, reject_autonomous_submission
from app.services.representation import evaluate_representation_risk

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Application]:
    return db.query(Application).order_by(Application.updated_at.desc()).limit(100).all()


@router.get("/queue", response_model=list[ApplicationOut])
def approval_queue(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Application]:
    states = [
        WorkflowState.PACKET_READY.value,
        WorkflowState.NEEDS_EDIT.value,
        WorkflowState.APPROVED_FOR_SUBMISSION.value,
    ]
    return db.query(Application).filter(Application.state.in_(states)).all()


@router.post("/jobs/{job_id}/generate", response_model=ApplicationOut)
def generate_packet(
    job_id: int,
    resume_profile: str = "qe_leadership",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        return generate_application_packet(
            db, job, actor=current_user.email, resume_profile=resume_profile
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/submit")
def submit_application(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    mode = payload.get("mode", "MANUAL")
    try:
        reject_autonomous_submission(mode)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    application_id = payload.get("application_id")
    if not application_id:
        raise HTTPException(status_code=400, detail="application_id required")
    application = db.query(Application).filter(Application.id == application_id).one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return {
        "status": "manual_required",
        "mode": mode,
        "message": "Open the official application URL and submit manually after review.",
        "application_id": application.id,
        "url": application.job.url if application.job else None,
        "actor": current_user.email,
    }


@router.post("/{application_id}/actions", response_model=ApplicationOut)
def approval_action(
    application_id: int,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    application = db.query(Application).filter(Application.id == application_id).one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        return apply_approval_action(
            db,
            application,
            action=payload.action,
            actor_email=current_user.email,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{application_id}/versions")
def application_versions(
    application_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    rows = list_versions(db, application_id)
    return [
        {
            "id": row.id,
            "version_number": row.version_number,
            "docx_path": row.docx_path,
            "pdf_path": row.pdf_path,
            "checksum_sha256": row.checksum_sha256,
            "is_submitted_immutable": row.is_submitted_immutable,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/{application_id}/timeline")
def application_timeline(
    application_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    rows = (
        db.query(ApplicationTimelineEvent)
        .filter(ApplicationTimelineEvent.application_id == application_id)
        .order_by(ApplicationTimelineEvent.created_at)
        .all()
    )
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "title": row.title,
            "description": row.description,
            "actor_email": row.actor_email,
            "created_at": row.created_at.isoformat(),
            "metadata": row.event_metadata,
        }
        for row in rows
    ]


@router.get("/jobs/{job_id}/apply-readiness")
def apply_readiness(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    dup = evaluate_duplicate_risk(db, job)
    rep = evaluate_representation_risk(db, job)
    return {
        "job_id": job_id,
        "official_url": job.url,
        "duplicate_risk": dup.to_dict(),
        "representation_risk": rep.to_dict(),
        "can_open_apply": dup.level.value != "RED" and rep.level.value != "RED",
        "message": "Aarohan has not submitted anything. Open the official employer URL only.",
    }
