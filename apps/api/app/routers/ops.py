from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.services.audit_labels import audit_event_label
from app.services.auth import process_recruiter_signal
from app.services.gmail_lifecycle import correct_classification, signal_to_public_dict

router = APIRouter(tags=["ops"])


@router.get("/environment")
def deployment_environment(_: User = Depends(get_current_user)) -> dict:
    from app.services.environment import environment_payload

    return environment_payload()


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


@router.get("/audit")
def audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    event_type: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            (AuditLog.event_type.ilike(like))
            | (AuditLog.actor.ilike(like))
            | (AuditLog.resource_id.ilike(like))
        )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "event_type": row.event_type,
                "event_label": audit_event_label(row.event_type),
                "actor": row.actor,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "details": row.details,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/connectors/runs")
def connector_run_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    query = (
        db.query(AuditLog)
        .filter(AuditLog.event_type == "connector.run")
        .order_by(AuditLog.created_at.desc())
    )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "provider": (row.details or {}).get("provider"),
                "job_count": (row.details or {}).get("job_count"),
                "fixture": (row.details or {}).get("fixture"),
                "actor": row.actor,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/ai/budget")
def ai_budget(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    return budget_status(db)


@router.get("/ai/usage")
def ai_usage(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    from app.config import settings

    query = db.query(AIUsageRecord).order_by(AIUsageRecord.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    budget = budget_status(db)
    synthetic = settings.oauth_fixture_mode or settings.app_env in {"test", "local"}
    return {
        "budget": {
            "monthly_spend_usd": budget["monthly_spend_usd"],
            "soft_cap_usd": budget["soft_cap_usd"],
            "hard_cap_usd": budget["hard_cap_usd"],
            "remaining_usd": round(max(budget["hard_cap_usd"] - budget["monthly_spend_usd"], 0), 4),
            "percent_of_hard_cap": budget["percent_of_hard_cap"],
            "note": "Spend totals are estimated from recorded usage rows, not vendor billing.",
        },
        "items": [
            {
                "id": row.id,
                "operation": row.operation,
                "model": row.model or "—",
                "cost_usd": row.cost_usd,
                "cost_label": "estimated" if synthetic else "recorded",
                "tokens_in": row.tokens_in,
                "tokens_out": row.tokens_out,
                "token_count": row.tokens_in + row.tokens_out,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/recruiter-signals")
def recruiter_signals(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    rows = db.query(RecruiterSignal).order_by(RecruiterSignal.received_at.desc()).limit(100).all()
    return [signal_to_public_dict(row) for row in rows]


@router.patch("/recruiter-signals/{signal_id}/classification")
def patch_signal_classification(
    signal_id: int,
    classification: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        signal = correct_classification(db, signal_id, classification, actor=current_user.email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return signal_to_public_dict(signal)


@router.post("/recruiter-signals")
def ingest_recruiter_signal(
    payload: RecruiterSignalRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    from app.config import settings

    if settings.app_env not in {"test", "local"} and not payload.gmail_message_id:
        raise HTTPException(
            status_code=403,
            detail="Manual recruiter signal ingest is disabled. Use Gmail sync.",
        )
    signal = process_recruiter_signal(db, payload.model_dump())
    return {"id": signal.id, "signal_type": signal.signal_type}
