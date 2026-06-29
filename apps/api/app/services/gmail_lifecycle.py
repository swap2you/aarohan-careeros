"""R2.7 Gmail inbound lifecycle: classify, dedupe, link, and ingest."""

from __future__ import annotations

from datetime import datetime, timedelta
from email.utils import parseaddr

from sqlalchemy.orm import Session

from app.models import Application, CompanyDomain, Job, ProcessedGmailMessage, RecruiterSignal, WorkflowState
from app.services.audit import write_audit
from app.services.gmail_alert_parsers import (
    JOB_ALERT_LABEL_PREFIX,
    parse_job_alert,
    parsed_job_to_ingest_payload,
)
from app.services.ingestion import ingest_job

JOB_ALERT = "JOB_ALERT"
RECRUITER_OUTREACH = "RECRUITER_OUTREACH"
APPLICATION_CONFIRMATION = "APPLICATION_CONFIRMATION"
ASSESSMENT = "ASSESSMENT"
INTERVIEW = "INTERVIEW"
REJECTION = "REJECTION"
OFFER = "OFFER"
FOLLOW_UP = "FOLLOW_UP"
UNRELATED = "UNRELATED"

LABEL_CLASSIFICATION_HINTS: dict[str, str] = {
    "Aarohan/Recruiters": RECRUITER_OUTREACH,
    "Aarohan/Interviews": INTERVIEW,
    "Aarohan/Applications": APPLICATION_CONFIRMATION,
    "Aarohan/Rejections": REJECTION,
    "Aarohan/Offers": OFFER,
    "Aarohan/Processing": UNRELATED,
}


def classify_message(message: dict, *, label: str | None = None) -> tuple[str, float]:
    if label and label.startswith(JOB_ALERT_LABEL_PREFIX):
        return JOB_ALERT, 0.9
    if label and label in LABEL_CLASSIFICATION_HINTS:
        return LABEL_CLASSIFICATION_HINTS[label], 0.88

    subject = (message.get("subject") or "").lower()
    body = (message.get("body_text") or "").lower()
    text = f"{subject}\n{body}"
    if any(k in text for k in ("offer", "compensation package", "pleased to extend")):
        return OFFER, 0.8
    if any(k in text for k in ("reject", "not moving forward", "other candidates")):
        return REJECTION, 0.85
    if any(k in text for k in ("interview", "schedule a call", "speak with you")):
        return INTERVIEW, 0.82
    if any(k in text for k in ("assessment", "codility", "hackerrank", "take-home")):
        return ASSESSMENT, 0.8
    if any(k in text for k in ("application received", "thank you for applying", "submitted your application")):
        return APPLICATION_CONFIRMATION, 0.78
    if any(k in text for k in ("following up", "follow up", "checking in")):
        return FOLLOW_UP, 0.75
    if any(k in text for k in ("recruiter", "talent acquisition", "hiring manager")):
        return RECRUITER_OUTREACH, 0.7
    if parse_job_alert(message, label=label):
        return JOB_ALERT, 0.72
    return UNRELATED, 0.5


def _snippet(body: str, limit: int = 240) -> str:
    return " ".join(body.split())[:limit]


def _resolve_company_id(db: Session, sender: str | None) -> int | None:
    if not sender:
        return None
    _, email = parseaddr(sender)
    if "@" not in email:
        return None
    domain = email.split("@", 1)[1].lower()
    row = db.query(CompanyDomain).filter(CompanyDomain.domain == domain).one_or_none()
    return row.company_id if row else None


def _resolve_application_id(db: Session, job_id: int | None) -> int | None:
    if not job_id:
        return None
    app = (
        db.query(Application)
        .filter(Application.job_id == job_id)
        .order_by(Application.id.desc())
        .first()
    )
    return app.id if app else None


def _find_linked_job(db: Session, message: dict) -> int | None:
    body = message.get("body_text") or ""
    for token in ("job #", "job id", "requisition"):
        if token in body.lower():
            digits = "".join(ch for ch in body.lower().split(token, 1)[-1][:12] if ch.isdigit())
            if digits:
                job = db.query(Job).filter(Job.id == int(digits)).one_or_none()
                if job:
                    return job.id
    return None


def _already_processed(db: Session, message_id: str | None) -> bool:
    if not message_id:
        return False
    return db.query(ProcessedGmailMessage).filter(ProcessedGmailMessage.message_id == message_id).first() is not None


def _mark_processed(db: Session, message_id: str | None) -> None:
    if not message_id or _already_processed(db, message_id):
        return
    db.add(ProcessedGmailMessage(message_id=message_id))
    db.commit()


def process_gmail_message(
    db: Session,
    message: dict,
    *,
    source: str = "gmail",
    label: str | None = None,
    actor: str = "gmail_sync",
) -> RecruiterSignal | None:
    message_id = message.get("id")
    thread_id = message.get("thread_id")
    if _already_processed(db, message_id):
        return None

    if message_id:
        existing = db.query(RecruiterSignal).filter(RecruiterSignal.gmail_message_id == message_id).one_or_none()
        if existing:
            _mark_processed(db, message_id)
            return existing

    signal_type, confidence = classify_message(message, label=label)
    body = message.get("body_text") or ""
    job_id = _find_linked_job(db, message)
    company_id = _resolve_company_id(db, message.get("sender"))

    if signal_type == JOB_ALERT:
        alert = parse_job_alert(message, label=label)
        if alert:
            job = ingest_job(db, parsed_job_to_ingest_payload(alert), actor=actor)
            job_id = job.id
            if not company_id:
                company_id = job.company_id
            confidence = max(confidence, alert.confidence)

    application_id = _resolve_application_id(db, job_id)
    follow_up_at = None
    if signal_type == RECRUITER_OUTREACH:
        follow_up_at = datetime.utcnow() + timedelta(days=5)

    if thread_id:
        thread_dup = (
            db.query(RecruiterSignal)
            .filter(
                RecruiterSignal.gmail_thread_id == thread_id,
                RecruiterSignal.signal_type == signal_type,
                RecruiterSignal.subject == message.get("subject"),
            )
            .one_or_none()
        )
        if thread_dup:
            _mark_processed(db, message_id)
            return thread_dup

    signal = RecruiterSignal(
        source=source,
        sender=message.get("sender"),
        subject=message.get("subject"),
        body_text=body,
        snippet=_snippet(body),
        signal_type=signal_type,
        job_id=job_id,
        application_id=application_id,
        company_id=company_id,
        gmail_message_id=message_id,
        gmail_thread_id=thread_id,
        gmail_label=label,
        classification_confidence=confidence,
        received_at=message.get("received_at") or datetime.utcnow(),
        processed=True,
        follow_up_at=follow_up_at,
    )
    db.add(signal)

    if job_id and signal_type == INTERVIEW:
        job = db.query(Job).filter(Job.id == job_id).one_or_none()
        if job:
            job.state = WorkflowState.INTERVIEW_SIGNAL.value
            db.add(job)
    if job_id and signal_type == OFFER:
        job = db.query(Job).filter(Job.id == job_id).one_or_none()
        if job:
            job.state = WorkflowState.OFFER.value
            db.add(job)
    if job_id and signal_type == REJECTION:
        job = db.query(Job).filter(Job.id == job_id).one_or_none()
        if job:
            job.state = WorkflowState.REJECTED_BY_EMPLOYER.value
            db.add(job)

    db.commit()
    db.refresh(signal)
    _mark_processed(db, message_id)
    write_audit(
        db,
        event_type="gmail.message_processed",
        actor=actor,
        resource_type="recruiter_signal",
        resource_id=str(signal.id),
        details={"signal_type": signal.signal_type, "label": label, "job_id": job_id},
    )
    return signal


def sync_messages(
    db: Session,
    messages: list[dict],
    *,
    source: str = "gmail",
    actor: str = "gmail_sync",
) -> dict:
    created: list[dict] = []
    skipped = 0
    jobs_ingested = 0
    for msg in messages:
        label = msg.get("label")
        before_jobs = db.query(Job).count()
        signal = process_gmail_message(db, msg, source=source, label=label, actor=actor)
        if not signal:
            skipped += 1
            continue
        after_jobs = db.query(Job).count()
        if after_jobs > before_jobs:
            jobs_ingested += 1
        created.append(
            {
                "id": signal.id,
                "signal_type": signal.user_classification_override or signal.signal_type,
                "job_id": signal.job_id,
                "gmail_message_id": signal.gmail_message_id,
            }
        )
    return {"processed": len(created), "skipped": skipped, "jobs_ingested": jobs_ingested, "signals": created}


def correct_classification(
    db: Session,
    signal_id: int,
    classification: str,
    *,
    actor: str,
) -> RecruiterSignal:
    signal = db.query(RecruiterSignal).filter(RecruiterSignal.id == signal_id).one_or_none()
    if not signal:
        raise ValueError("Signal not found")
    signal.user_classification_override = classification
    db.add(signal)
    db.commit()
    db.refresh(signal)
    write_audit(
        db,
        event_type="gmail.classification_corrected",
        actor=actor,
        resource_type="recruiter_signal",
        resource_id=str(signal.id),
        details={"classification": classification},
    )
    return signal


def signal_to_public_dict(row: RecruiterSignal) -> dict:
    return {
        "id": row.id,
        "signal_type": row.user_classification_override or row.signal_type,
        "original_classification": row.signal_type,
        "sender": row.sender,
        "subject": row.subject,
        "snippet": row.snippet,
        "job_id": row.job_id,
        "application_id": row.application_id,
        "company_id": row.company_id,
        "gmail_label": row.gmail_label,
        "classification_confidence": row.classification_confidence,
        "user_classification_override": row.user_classification_override,
        "received_at": row.received_at.isoformat() if row.received_at else None,
        "follow_up_at": row.follow_up_at.isoformat() if row.follow_up_at else None,
    }
