import bcrypt
from datetime import datetime, timedelta

from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models import RecruiterSignal, WorkflowState

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str, expires_minutes: int = 60 * 12) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.app_secret, algorithm=ALGORITHM)


def process_recruiter_signal(db: Session, payload: dict) -> RecruiterSignal:
    body = payload.get("body_text", "")
    lowered = body.lower()
    if "interview" in lowered or "schedule" in lowered:
        signal_type = "INTERVIEW_SIGNAL"
    elif "reject" in lowered or "not moving forward" in lowered:
        signal_type = "REJECTION"
    else:
        signal_type = "RECRUITER_RESPONSE"

    signal = RecruiterSignal(
        source=payload.get("source", "gmail"),
        sender=payload.get("sender"),
        subject=payload.get("subject"),
        body_text=body,
        signal_type=signal_type,
        job_id=payload.get("job_id"),
        processed=True,
    )
    db.add(signal)
    if payload.get("job_id") and signal_type == "INTERVIEW_SIGNAL":
        from app.models import Job

        job = db.query(Job).filter(Job.id == payload["job_id"]).one_or_none()
        if job:
            job.state = WorkflowState.INTERVIEW_SIGNAL.value
            db.add(job)
    db.commit()
    db.refresh(signal)
    return signal
