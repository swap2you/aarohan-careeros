"""Discovery Control Center API (Workflow 01.5).

Endpoints for the versioned owner discovery policy, presets, source inventory, unified
discovery runs, diagnostics, per-job explainability, and manual opportunities.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ConnectorRun, Job, JobOrigin, User
from app.services import discovery_policy_service as pol
from app.services.discovery_explain import build_job_explanation
from app.services.discovery_orchestration import (
    run_all_discovery,
    run_gmail_discovery,
)
from app.services.discovery_origin import manual_opportunity_dict, set_manual_status
from app.services.discovery_policy import (
    discovery_policy_defaults,
    job_discovery_policy,
)
from app.services.discovery_source_inventory import build_source_inventory
from app.services.fresh_jobs_discovery import discover_fresh_jobs

router = APIRouter(prefix="/discovery", tags=["discovery"])


class OverridePayload(BaseModel):
    overrides: dict = Field(default_factory=dict)
    preset: str | None = None
    label: str | None = None
    notes: str | None = None


class PreviewPayload(BaseModel):
    overrides: dict = Field(default_factory=dict)
    sample_limit: int = 8


class RunPayload(BaseModel):
    use_fixture: bool = False


class ManualStatusPayload(BaseModel):
    status: str


def _version_dict(v) -> dict:
    return {
        "id": v.id,
        "version": v.version,
        "status": v.status,
        "preset": v.preset,
        "label": v.label,
        "notes": v.notes,
        "overrides": v.overrides,
        "created_by": v.created_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "activated_by": v.activated_by,
        "activated_at": v.activated_at.isoformat() if v.activated_at else None,
    }


# ---- Policy -------------------------------------------------------------------------
@router.get("/policy/effective")
def get_effective_policy(_: User = Depends(get_current_user)) -> dict:
    return {"policy": job_discovery_policy()}


@router.get("/policy/defaults")
def get_defaults(_: User = Depends(get_current_user)) -> dict:
    return {"policy": discovery_policy_defaults()}


@router.get("/policy/versions")
def get_versions(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    return {"versions": [_version_dict(v) for v in pol.list_versions(db)]}


@router.get("/policy/active")
def get_active(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    active = pol.get_active_version(db)
    return {"active": _version_dict(active) if active else None}


@router.post("/policy/preview")
def preview(payload: PreviewPayload, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    try:
        return pol.preview_policy(db, payload.overrides, sample_limit=payload.sample_limit)
    except pol.PolicyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/policy/draft")
def create_draft(payload: OverridePayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    try:
        version = pol.create_draft(
            db,
            payload.overrides,
            preset=payload.preset,
            label=payload.label,
            notes=payload.notes,
            created_by=current_user.email,
        )
    except pol.PolicyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"version": _version_dict(version)}


@router.post("/policy/{version_id}/activate")
def activate(version_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    try:
        version = pol.activate_version(db, version_id, activated_by=current_user.email)
    except pol.PolicyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"version": _version_dict(version), "effective_policy": job_discovery_policy()}


@router.post("/policy/restore-defaults")
def restore_defaults(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    version = pol.restore_defaults(db, actor=current_user.email)
    return {"version": _version_dict(version), "effective_policy": job_discovery_policy()}


# ---- Presets ------------------------------------------------------------------------
@router.get("/presets")
def list_presets(_: User = Depends(get_current_user)) -> dict:
    return {
        "presets": [
            {"name": name, "overrides": pol.preset_overrides(name)} for name in pol.preset_names()
        ],
        "default": "balanced",
    }


# ---- Sources & diagnostics ----------------------------------------------------------
@router.get("/sources")
def sources(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    return build_source_inventory(db)


@router.get("/runs")
def runs(limit: int = 20, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    limit = max(1, min(limit, 50))
    rows = db.execute(
        select(ConnectorRun).order_by(ConnectorRun.started_at.desc()).limit(limit)
    ).scalars().all()
    return {
        "runs": [
            {
                "id": r.id,
                "provider": r.provider,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "health_state": r.health_state,
                "fetched": r.fetched_count,
                "accepted": r.accepted_count,
                "owner_review": r.secondary_review_count,
                "quarantined": r.quarantined_count,
                "rejected": r.rejected_count,
                "duplicate": r.duplicate_count,
                "reason_distribution": r.reason_distribution or {},
                "error_redacted": r.error_redacted,
                "actor": r.actor,
            }
            for r in rows
        ]
    }


@router.get("/runs/{run_id}")
def run_detail(run_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    run = db.get(ConnectorRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "id": run.id,
        "provider": run.provider,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "health_state": run.health_state,
        "search_profile": run.search_profile,
        "counts": {
            "fetched": run.fetched_count,
            "accepted": run.accepted_count,
            "owner_review": run.secondary_review_count,
            "quarantined": run.quarantined_count,
            "rejected": run.rejected_count,
            "duplicate": run.duplicate_count,
            "archived": run.archived_count,
        },
        "reason_distribution": run.reason_distribution or {},
        "error_redacted": run.error_redacted,
        "actor": run.actor,
        "latency_ms": run.latency_ms,
    }


@router.get("/diagnostics")
def diagnostics(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    inventory = build_source_inventory(db)
    recent = db.execute(
        select(ConnectorRun).order_by(ConnectorRun.started_at.desc()).limit(20)
    ).scalars().all()
    return {
        "inventory": inventory,
        "recent_runs": [
            {
                "id": r.id,
                "provider": r.provider,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "health_state": r.health_state,
                "fetched": r.fetched_count,
                "accepted": r.accepted_count,
                "rejected": r.rejected_count,
            }
            for r in recent
        ],
    }


# ---- Runs (orchestration) -----------------------------------------------------------
@router.post("/run")
def run_all(payload: RunPayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    return run_all_discovery(db, actor=current_user.email, use_fixture=payload.use_fixture)


@router.post("/run/gmail")
def run_gmail(payload: RunPayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    return run_gmail_discovery(db, actor=current_user.email, use_fixture=payload.use_fixture)


@router.post("/run/public")
def run_public(payload: RunPayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    return discover_fresh_jobs(db, actor=current_user.email, use_fixture=payload.use_fixture)


# ---- Explainability & manual opportunities ------------------------------------------
@router.get("/jobs/{job_id}/explain")
def explain_job(job_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return build_job_explanation(db, job)


@router.get("/opportunities")
def opportunities(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    rows = (
        db.query(Job)
        .filter((Job.origin == JobOrigin.OWNER_ADDED.value) | (Job.manual_status.is_not(None)))
        .order_by(Job.added_at.desc().nullslast(), Job.id.desc())
        .all()
    )
    return {"opportunities": [manual_opportunity_dict(j) for j in rows]}


@router.post("/opportunities/{job_id}/status")
def set_status(job_id: int, payload: ManualStatusPayload, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    try:
        set_manual_status(job, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(job)
    return {"opportunity": manual_opportunity_dict(job)}
