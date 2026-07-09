from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.integrations.job_sources import FixtureFeedAdapter, GreenhouseAdapter, LeverAdapter
from app.models import Job, JobScore, User, WorkflowState
from app.schemas import JobIngestRequest, JobOut
from app.services.job_detail import build_job_detail
from app.services.ingestion import ingest_job
from app.services.provenance import OWNER_EXCLUDED, infer_provenance
from app.services.scoring import score_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _owner_jobs_query(db: Session, *, include_fixture: bool = False):
    query = db.query(Job)
    if not include_fixture:
        query = query.filter(~Job.data_provenance.in_(OWNER_EXCLUDED))
    return query


@router.get("")
def list_jobs(
    state: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = None,
    source: str | None = None,
    company: str | None = None,
    role_family: str | None = None,
    workplace_type: str | None = None,
    application_state: str | None = None,
    sort_by: str = Query("newest", pattern="^(newest|fit|trust|salary|company|title)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    include_fixture: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    query = _owner_jobs_query(db, include_fixture=include_fixture)
    if state:
        query = query.filter(Job.state == state)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter((Job.title.ilike(like)) | (Job.company.ilike(like)))
    if source:
        query = query.filter(Job.source.ilike(f"%{source.strip()}%"))
    if company:
        query = query.filter(Job.company.ilike(f"%{company.strip()}%"))
    if role_family:
        query = query.filter(Job.role_family == role_family)
    if workplace_type:
        query = query.filter(Job.workplace_type == workplace_type)
    if application_state:
        from app.models import Application

        query = query.join(Application, Application.job_id == Job.id).filter(Application.state == application_state)

    total = query.count()

    score_order = asc if sort_dir == "asc" else desc
    job_order = asc if sort_dir == "asc" else desc

    if sort_by in {"fit", "trust", "salary"}:
        query = query.outerjoin(JobScore, JobScore.job_id == Job.id)
        if sort_by == "fit":
            query = query.order_by(score_order(JobScore.total_score).nulls_last(), desc(Job.discovered_at))
        elif sort_by == "trust":
            query = query.order_by(score_order(JobScore.trust_score).nulls_last(), desc(Job.discovered_at))
        else:
            query = query.order_by(job_order(Job.salary_max).nulls_last(), desc(Job.discovered_at))
    elif sort_by == "company":
        query = query.order_by(asc(Job.company), desc(Job.discovered_at))
    elif sort_by == "title":
        query = query.order_by(asc(Job.title), desc(Job.discovered_at))
    else:
        query = query.order_by(desc(Job.discovered_at))

    rows = query.options(joinedload(Job.score)).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [JobOut.model_validate(row).model_dump(mode="json") for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
    }


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


@router.get("/{job_id}/detail")
def get_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return build_job_detail(db, job)


@router.post("/ingest", response_model=JobOut)
def ingest_single_job(
    payload: JobIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    data = payload.model_dump()
    if not data.get("data_provenance"):
        data["data_provenance"] = infer_provenance(data.get("source", ""), payload=data)
    return ingest_job(db, data, actor=current_user.email)


@router.post("/ingest/fixture", response_model=list[JobOut])
def ingest_fixture_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Job]:
    adapter = FixtureFeedAdapter()
    jobs = []
    for item in adapter.fetch_jobs():
        item["data_provenance"] = "fixture"
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
        item["data_provenance"] = "connector"
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
        item["data_provenance"] = "connector"
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
