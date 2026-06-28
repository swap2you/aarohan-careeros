from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import InterviewPack, Job, User
from app.schemas import InterviewPackOut
from app.services.interview import generate_interview_pack, score_exercise

router = APIRouter(prefix="/interviews", tags=["interviews"])


class ExerciseScoreRequest(BaseModel):
    exercise_id: str
    scores: dict[str, float]


@router.get("/{job_id}", response_model=InterviewPackOut)
def get_interview_pack(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> InterviewPack:
    pack = db.query(InterviewPack).filter(InterviewPack.job_id == job_id).one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Interview pack not found")
    return pack


@router.post("/jobs/{job_id}/generate", response_model=InterviewPackOut)
def create_interview_pack(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewPack:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return generate_interview_pack(db, job, actor=current_user.email)


@router.post("/jobs/{job_id}/exercises/score", response_model=InterviewPackOut)
def score_interview_exercise(
    job_id: int,
    payload: ExerciseScoreRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> InterviewPack:
    pack = db.query(InterviewPack).filter(InterviewPack.job_id == job_id).one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Interview pack not found")
    return score_exercise(db, pack, payload.exercise_id, payload.scores)
