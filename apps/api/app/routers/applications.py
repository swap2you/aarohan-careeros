from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Application, ApplicationTimelineEvent, Job, User, WorkflowState
from app.schemas import ApplicationOut, ApprovalRequest
from app.services.application_summary import serialize_application
from app.services.approval import apply_approval_action
from app.services.document_versions import list_versions
from app.services.documents import generate_application_packet
from app.services.duplicate_risk import evaluate_duplicate_risk, reject_autonomous_submission
from app.services.representation import evaluate_representation_risk
from app.services.provenance import OWNER_EXCLUDED
from app.services.packet_artifacts import list_packet_artifacts

router = APIRouter(prefix="/applications", tags=["applications"])


def _owner_applications_query(db: Session):
    return (
        db.query(Application)
        .join(Job)
        .options(joinedload(Application.job))
        .filter(~Application.data_provenance.in_(OWNER_EXCLUDED))
        .filter(~Job.data_provenance.in_(OWNER_EXCLUDED))
    )


@router.get("")
def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    state: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    query = _owner_applications_query(db).order_by(Application.updated_at.desc())
    if state:
        query = query.filter(Application.state == state)
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialize_application(row, db=db) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/queue")
def approval_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    states = [
        WorkflowState.PACKET_READY.value,
        WorkflowState.NEEDS_EDIT.value,
        WorkflowState.APPROVED_FOR_SUBMISSION.value,
    ]
    query = (
        _owner_applications_query(db)
        .filter(Application.state.in_(states))
        .order_by(Application.updated_at.desc())
    )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialize_application(row, db=db) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/{application_id}/packet")
def get_packet_manifest(
    application_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    application = db.query(Application).filter(Application.id == application_id).one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return list_packet_artifacts(application)


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
