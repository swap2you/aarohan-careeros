from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.integrations.job_sources import FixtureFeedAdapter
from app.models import Job, User, WorkflowState
from app.services.audit import write_audit
from app.services.fresh_jobs_discovery import discover_fresh_jobs
from app.services.ingestion import ingest_job
from app.services.scoring import score_job

router = APIRouter(prefix="/workflows", tags=["workflows"])


class ImportUrlRequest(BaseModel):
    url: str
    title: str | None = None
    company: str | None = None


class GeneratePacketsRequest(BaseModel):
    job_ids: list[int]
    resume_profile: str = "qe_leadership"


class WorkflowResult(BaseModel):
    action: str
    success: int = 0
    failed: int = 0
    details: list[dict] = []
    # Extended discovery stats (UI ignores unknown fields safely via JSON)
    fetched: int = 0
    accepted: int = 0
    owner_review: int = 0
    secondary_review: int = 0
    quarantined: int = 0
    rejected: int = 0
    duplicates: int = 0
    sources: list[dict] = []
    sources_attempted: list[dict] = []
    sources_skipped: list[dict] = []
    source_errors: list[dict] = []
    message: str | None = None


@router.post("/ingest/fixture", response_model=WorkflowResult)
def workflow_ingest_fixture(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowResult:
    adapter = FixtureFeedAdapter()
    details = []
    for item in adapter.fetch_jobs():
        item["data_provenance"] = "fixture"
        job = ingest_job(db, item, actor=current_user.email)
        details.append({"job_id": job.id, "title": job.title, "status": "ok"})
    write_audit(db, event_type="workflow.ingest_fixture", actor=current_user.email, details={"count": len(details)})
    return WorkflowResult(action="ingest_fixture", success=len(details), details=details)


@router.post("/discover-fresh-jobs")
def workflow_discover_fresh_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = discover_fresh_jobs(db, actor=current_user.email)
    write_audit(
        db,
        event_type="workflow.discover_fresh_jobs",
        actor=current_user.email,
        details={
            "fetched": result.get("fetched"),
            "accepted": result.get("accepted"),
            "rejected": result.get("rejected"),
            "quarantined": result.get("quarantined"),
            "duplicates": result.get("duplicates"),
        },
    )
    return result


@router.post("/ingest/public", response_model=WorkflowResult)
def workflow_ingest_public(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowResult:
    """Backward-compatible path used by the locked Fresh Jobs UI button.

    Internally runs the policy-driven discovery campaign — never a hardcoded
    single-company Greenhouse board.
    """
    result = discover_fresh_jobs(db, actor=current_user.email)
    write_audit(
        db,
        event_type="workflow.ingest_public",
        actor=current_user.email,
        details={
            "action": "discover_fresh_jobs",
            "fetched": result.get("fetched"),
            "accepted": result.get("accepted"),
            "rejected": result.get("rejected"),
        },
    )
    return WorkflowResult(
        action="discover_fresh_jobs",
        success=int(result.get("accepted") or 0),
        failed=int(result.get("rejected") or 0),
        details=result.get("sources") or [],
        fetched=int(result.get("fetched") or 0),
        accepted=int(result.get("accepted") or 0),
        owner_review=int(result.get("owner_review") or 0),
        secondary_review=int(result.get("secondary_review") or 0),
        quarantined=int(result.get("quarantined") or 0),
        rejected=int(result.get("rejected") or 0),
        duplicates=int(result.get("duplicates") or 0),
        sources=result.get("sources") or [],
        sources_attempted=result.get("sources_attempted") or [],
        sources_skipped=result.get("sources_skipped") or [],
        source_errors=result.get("source_errors") or [],
        message=result.get("message"),
    )


@router.post("/import-url", response_model=WorkflowResult)
def workflow_import_url(
    payload: ImportUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowResult:
    """URL-only import returns NEEDS_CONFIRMATION — never auto-accept as a Fresh Job."""
    from app.services.gmail_alert_parsers import canonical_job_url
    from app.services.ingestion import ingest_job_with_decision

    url = canonical_job_url(payload.url) if payload.url else payload.url
    existing = (
        db.query(Job)
        .filter(Job.source == "user_forwarded_links", Job.external_id == url)
        .one_or_none()
    )
    if existing is None and url:
        existing = db.query(Job).filter(Job.canonical_url == url).one_or_none()
    if existing is not None:
        return WorkflowResult(
            action="import_url",
            success=0,
            details=[
                {
                    "job_id": existing.id,
                    "url": url,
                    "status": "DUPLICATE",
                    "decision": existing.ingest_decision,
                    "message": "Existing job returned for duplicate URL import",
                }
            ],
            message=f"Duplicate URL — existing job_id={existing.id}",
        )

    title_provided = bool((payload.title or "").strip())
    company_provided = bool((payload.company or "").strip())
    if not title_provided or not company_provided:
        return WorkflowResult(
            action="import_url",
            success=0,
            details=[
                {
                    "url": url,
                    "status": "NEEDS_CONFIRMATION",
                    "decision": "NEEDS_CONFIRMATION",
                    "message": "URL-only import requires owner confirmation of title and company",
                }
            ],
            message="NEEDS_CONFIRMATION: provide title and company, or use New Opportunity confirm flow",
        )

    item = {
        "source": "user_forwarded_links",
        "external_id": url,
        "title": payload.title,
        "company": payload.company,
        "url": url,
        "canonical_url": url,
        "description_html": "",
        "description_text": "User forwarded job link. Owner-confirmed title/company.",
        "owner_confirmed": True,
        "manual_confirmed": True,
        "discovered_at": None,
    }
    outcome = ingest_job_with_decision(db, item, actor=current_user.email, allow_discovered_at=True)
    job = outcome.job
    return WorkflowResult(
        action="import_url",
        success=1 if job else 0,
        details=[
            {
                "job_id": job.id if job else None,
                "url": url,
                "status": "ok" if job else "rejected",
                "decision": outcome.decision,
            }
        ],
    )


@router.post("/score-all", response_model=WorkflowResult)
def workflow_score_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowResult:
    jobs = db.query(Job).filter(Job.state.in_([WorkflowState.INGESTED.value, WorkflowState.NORMALIZED.value])).all()
    details = []
    for job in jobs:
        score_job(db, job)
        details.append({"job_id": job.id, "score": job.score.total_score if job.score else None})
    return WorkflowResult(action="score_all", success=len(details), details=details)


@router.post("/generate-packets", response_model=WorkflowResult)
def workflow_generate_packets(
    payload: GeneratePacketsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowResult:
    from app.services.documents import generate_application_packet

    details = []
    failed = 0
    for job_id in payload.job_ids:
        job = db.query(Job).filter(Job.id == job_id).one_or_none()
        if not job:
            failed += 1
            details.append({"job_id": job_id, "status": "not_found"})
            continue
        try:
            app = generate_application_packet(
                db, job, actor=current_user.email, resume_profile=payload.resume_profile
            )
            details.append({"job_id": job_id, "application_id": app.id, "status": "ok"})
        except Exception as exc:
            failed += 1
            details.append({"job_id": job_id, "status": "error", "message": str(exc)})
    return WorkflowResult(
        action="generate_packets",
        success=len(payload.job_ids) - failed,
        failed=failed,
        details=details,
    )
