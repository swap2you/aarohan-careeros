from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    AIUsageRecord,
    Application,
    AuditLog,
    ConsultingLead,
    InterviewPack,
    Job,
    RecruiterSignal,
    User,
    WorkflowState,
)
from app.schemas import AnalyticsOut, AuditLogOut, RecruiterSignalRequest
from app.services.ai_budget import budget_status
from app.services.auth import process_recruiter_signal

router = APIRouter(tags=["ops"])


@router.get("/analytics", response_model=AnalyticsOut)
def analytics(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> AnalyticsOut:
    return AnalyticsOut(
        total_jobs=db.query(Job).count(),
        shortlisted_jobs=db.query(Job).filter(Job.state == WorkflowState.SHORTLISTED.value).count(),
        applications_ready=db.query(Application)
        .filter(Application.state == WorkflowState.PACKET_READY.value)
        .count(),
        submitted_applications=db.query(Application)
        .filter(Application.state == WorkflowState.SUBMITTED.value)
        .count(),
        consulting_leads=db.query(ConsultingLead).count(),
        interview_packs=db.query(InterviewPack).count(),
    )


@router.get("/audit", response_model=list[AuditLogOut])
def audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AuditLog]:
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()


@router.get("/ai/budget")
def ai_budget(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    return budget_status(db)


@router.get("/ai/usage")
def ai_usage(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    rows = db.query(AIUsageRecord).order_by(AIUsageRecord.created_at.desc()).limit(100).all()
    return [
        {
            "id": row.id,
            "operation": row.operation,
            "cost_usd": row.cost_usd,
            "model": row.model,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/recruiter-signals")
def recruiter_signals(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    rows = db.query(RecruiterSignal).order_by(RecruiterSignal.received_at.desc()).limit(100).all()
    return [
        {
            "id": row.id,
            "signal_type": row.signal_type,
            "sender": row.sender,
            "subject": row.subject,
            "job_id": row.job_id,
            "received_at": row.received_at.isoformat(),
        }
        for row in rows
    ]


@router.post("/recruiter-signals")
def ingest_recruiter_signal(
    payload: RecruiterSignalRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    signal = process_recruiter_signal(db, payload.model_dump())
    return {"id": signal.id, "signal_type": signal.signal_type}
