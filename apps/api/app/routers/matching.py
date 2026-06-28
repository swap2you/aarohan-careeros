from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Job, User
from app.schemas import JobOut
from app.services.scoring import score_job
from app.services.trust_matching import analyze_job, get_preferences

router = APIRouter(prefix="/matching", tags=["matching"])


@router.get("/preferences")
def matching_preferences(_: User = Depends(get_current_user)) -> dict:
    return get_preferences()


@router.get("/jobs/{job_id}/card")
def job_match_card(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job or not job.score:
        raise HTTPException(status_code=404, detail="Job or score not found")
    analysis = analyze_job(db, job, job.score)
    return analysis.to_dict()


@router.post("/jobs/{job_id}/rescore", response_model=JobOut)
def rescore_with_matching(
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
