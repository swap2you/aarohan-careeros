from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.integrations.job_sources import FixtureFeedAdapter, GreenhouseAdapter, LeverAdapter
from app.models import Job, User, WorkflowState
from app.schemas import JobIngestRequest, JobOut
from app.services.ingestion import ingest_job
from app.services.scoring import score_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    state: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Job]:
    query = db.query(Job).order_by(Job.discovered_at.desc())
    if state:
        query = query.filter(Job.state == state)
    return query.limit(100).all()


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Job:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/ingest", response_model=JobOut)
def ingest_single_job(
    payload: JobIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    return ingest_job(db, payload.model_dump(), actor=current_user.email)


@router.post("/ingest/fixture", response_model=list[JobOut])
def ingest_fixture_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Job]:
    adapter = FixtureFeedAdapter()
    jobs = []
    for item in adapter.fetch_jobs():
        jobs.append(ingest_job(db, item, actor=current_user.email))
    return jobs


@router.post("/ingest/greenhouse/{board_token}", response_model=list[JobOut])
def ingest_greenhouse(
    board_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Job]:
    adapter = GreenhouseAdapter(board_token)
    jobs = []
    for item in adapter.fetch_jobs():
        jobs.append(ingest_job(db, item, actor=current_user.email))
    return jobs


@router.post("/ingest/lever/{company_slug}", response_model=list[JobOut])
def ingest_lever(
    company_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Job]:
    adapter = LeverAdapter(company_slug)
    jobs = []
    for item in adapter.fetch_jobs():
        jobs.append(ingest_job(db, item, actor=current_user.email))
    return jobs


@router.post("/{job_id}/rescore", response_model=JobOut)
def rescore_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Job:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    score_job(db, job)
    db.refresh(job)
    return job
