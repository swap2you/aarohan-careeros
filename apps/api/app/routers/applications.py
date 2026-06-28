from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Application, Job, User, WorkflowState
from app.schemas import ApplicationOut, ApprovalRequest
from app.services.approval import apply_approval_action
from app.services.documents import generate_application_packet

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
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    return apply_approval_action(
        db,
        application,
        action=payload.action,
        actor_email=current_user.email,
        notes=payload.notes,
    )
