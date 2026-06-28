"""Representation record API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Job, RepresentationOverride, RepresentationRecord, User
from app.services.audit import write_audit
from app.services.duplicate_risk import normalize_company_name
from app.services.representation import evaluate_representation_risk

router = APIRouter(prefix="/representations", tags=["representations"])


class RepresentationIn(BaseModel):
    vendor_name: str
    client_name: str
    requisition_id: str | None = None
    role_title: str | None = None
    status: str = "active"
    recruiter_contact: str | None = None
    source_evidence: str | None = None
    notes: str | None = None
    no_agreement_confirmed: bool = False
    representation_end: str | None = None


class OverrideIn(BaseModel):
    reason: str = Field(min_length=10)


@router.get("")
def list_representations(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    rows = db.query(RepresentationRecord).order_by(RepresentationRecord.updated_at.desc()).limit(100).all()
    return [
        {
            "id": row.id,
            "vendor_name": row.vendor_name,
            "client_name": row.client_name,
            "requisition_id": row.requisition_id,
            "role_title": row.role_title,
            "status": row.status,
            "representation_end": row.representation_end.isoformat() if row.representation_end else None,
        }
        for row in rows
    ]


@router.post("")
def create_representation(
    payload: RepresentationIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    end = None
    if payload.representation_end:
        end = datetime.fromisoformat(payload.representation_end.replace("Z", "+00:00")).replace(tzinfo=None)
    row = RepresentationRecord(
        vendor_name=payload.vendor_name.strip(),
        client_name=payload.client_name.strip(),
        normalized_client=normalize_company_name(payload.client_name),
        requisition_id=payload.requisition_id,
        role_title=payload.role_title,
        status=payload.status,
        recruiter_contact=payload.recruiter_contact,
        source_evidence=payload.source_evidence,
        notes=payload.notes,
        no_agreement_confirmed=payload.no_agreement_confirmed,
        representation_end=end,
        created_by=current_user.email,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(
        db,
        event_type="representation.created",
        actor=current_user.email,
        resource_type="representation",
        resource_id=str(row.id),
        details={"vendor": row.vendor_name, "client": row.client_name},
    )
    return {"id": row.id}


@router.get("/jobs/{job_id}/representation-risk")
def job_representation_risk(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return evaluate_representation_risk(db, job).to_dict()


@router.post("/jobs/{job_id}/representation-override")
def override_representation_risk(
    job_id: int,
    payload: OverrideIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    row = RepresentationOverride(
        job_id=job_id,
        reason=payload.reason,
        actor_email=current_user.email,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    write_audit(
        db,
        event_type="representation.override",
        actor=current_user.email,
        resource_type="job",
        resource_id=str(job_id),
        details={"reason": payload.reason},
    )
    db.commit()
    return {"overridden": True, "job_id": job_id}
