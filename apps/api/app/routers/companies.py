from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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


@router.get("", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Company]:
    return db.query(Company).order_by(Company.canonical_name).limit(200).all()


@router.get("/ledger", response_model=list[LedgerOut])
def list_ledger(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[ApplicationLedger]:
    return db.query(ApplicationLedger).order_by(ApplicationLedger.updated_at.desc()).limit(100).all()


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
