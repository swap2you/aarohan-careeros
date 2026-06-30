from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ApplicationLedger, Company, CompanyAlias, DuplicateOverride, Job, User
from app.services.audit import write_audit
from app.services.duplicate_risk import (
    AUTONOMOUS_REJECT_MESSAGE,
    ApplicationMode,
    evaluate_duplicate_risk,
    reject_autonomous_submission,
)
from app.services.provenance import OWNER_EXCLUDED

router = APIRouter(prefix="/companies", tags=["companies"])


class CompanyOut(BaseModel):
    id: int
    canonical_name: str
    normalized_name: str

    model_config = {"from_attributes": True}


class LedgerOut(BaseModel):
    id: int
    company_id: int
    job_id: int | None
    status: str
    normalized_title: str | None
    submitted_at: datetime | None

    model_config = {"from_attributes": True}


class OverrideRequest(BaseModel):
    reason: str = Field(min_length=10)


@router.get("")
def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    query = db.query(Company).filter(~Company.data_provenance.in_(OWNER_EXCLUDED))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            (Company.canonical_name.ilike(like)) | (Company.normalized_name.ilike(like))
        )
    query = query.order_by(Company.canonical_name)
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for row in rows:
        app_count = db.query(ApplicationLedger).filter(ApplicationLedger.company_id == row.id).count()
        items.append(
            {
                "id": row.id,
                "canonical_name": row.canonical_name,
                "normalized_name": row.normalized_name,
                "data_provenance": row.data_provenance,
                "application_count": app_count,
            }
        )
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/ledger")
def list_ledger(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    query = (
        db.query(ApplicationLedger)
        .join(Company)
        .options(joinedload(ApplicationLedger.company))
        .filter(~Company.data_provenance.in_(OWNER_EXCLUDED))
        .order_by(ApplicationLedger.updated_at.desc())
    )
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            (Company.canonical_name.ilike(like)) | (ApplicationLedger.normalized_title.ilike(like))
        )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "company_id": row.company_id,
                "company_name": row.company.canonical_name if row.company else None,
                "job_id": row.job_id,
                "status": row.status,
                "normalized_title": row.normalized_title,
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/jobs/{job_id}/duplicate-risk")
def job_duplicate_risk(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = evaluate_duplicate_risk(db, job)
    return result.to_dict()


@router.post("/jobs/{job_id}/duplicate-override")
def override_duplicate_risk(
    job_id: int,
    payload: OverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    risk = evaluate_duplicate_risk(db, job)
    if not risk.can_override and risk.level.value == "GREEN":
        raise HTTPException(status_code=400, detail="No override needed")
    row = DuplicateOverride(
        job_id=job_id,
        risk_level=risk.level.value,
        reason=payload.reason,
        actor_email=current_user.email,
        policy_version=risk.policy_version,
        matched_records=risk.matched_ledger_ids,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    write_audit(
        db,
        event_type="duplicate.override",
        actor=current_user.email,
        resource_type="job",
        resource_id=str(job_id),
        details={"reason": payload.reason, "risk": risk.level.value},
    )
    db.commit()
    return {"overridden": True, "job_id": job_id}


@router.post("/application-modes/validate")
def validate_application_mode(payload: dict, _: User = Depends(get_current_user)) -> dict:
    mode = payload.get("mode", ApplicationMode.MANUAL.value)
    try:
        reject_autonomous_submission(mode)
        return {"allowed": True, "mode": mode}
    except ValueError as exc:
        return {"allowed": False, "mode": mode, "message": str(exc)}


@router.get("/application-modes")
def list_application_modes(_: User = Depends(get_current_user)) -> dict:
    return {
        "modes": [
            {
                "id": ApplicationMode.MANUAL.value,
                "label": "Manual",
                "description": "Generate packet and open official application URL. No external form filling.",
                "enabled": True,
            },
            {
                "id": ApplicationMode.ASSISTED.value,
                "label": "Assisted",
                "description": "Prepare supported Greenhouse, Lever, and Ashby fields. Stops before employer Submit.",
                "enabled": True,
            },
            {
                "id": ApplicationMode.AUTONOMOUS_LOCKED.value,
                "label": "Autonomous (locked)",
                "description": AUTONOMOUS_REJECT_MESSAGE,
                "enabled": False,
            },
        ]
    }
