"""R2.9 Ask Aarohan read-only Q&A over internal records."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models import Application, Company, InterviewPack, Job, RecruiterSignal
from app.services.audit import write_audit

BLOCKED_TABLES = {"oauth_tokens", "user_sessions", "users"}


def _citations(*pairs: tuple[str, str | int]) -> list[dict]:
    return [{"type": t, "id": str(i)} for t, i in pairs]


def answer_question(db: Session, question: str, *, actor: str) -> dict:
    q = question.strip().lower()
    write_audit(
        db,
        event_type="ask_aarohan.query",
        actor=actor,
        resource_type="ask",
        resource_id="query",
        details={"question_length": len(question)},
    )

    if any(word in q for word in ("secret", "password", "token", "oauth")):
        return {
            "answer": "I cannot access or disclose authentication secrets or OAuth tokens.",
            "citations": [],
            "uncertainty": "blocked_policy",
        }

    if "how many jobs" in q or "total jobs" in q:
        count = db.query(Job).count()
        return {
            "answer": f"There are {count} jobs in the pipeline.",
            "citations": _citations(("jobs", "collection")),
            "uncertainty": None,
        }

    if "applications" in q and ("ready" in q or "packet" in q):
        from app.models import WorkflowState

        count = db.query(Application).filter(Application.state == WorkflowState.PACKET_READY.value).count()
        return {
            "answer": f"{count} applications are in PACKET_READY state.",
            "citations": _citations(("applications", "state:PACKET_READY")),
            "uncertainty": None,
        }

    job_match = re.search(r"job\s*#?(\d+)", q)
    if job_match:
        job_id = int(job_match.group(1))
        job = db.query(Job).filter(Job.id == job_id).one_or_none()
        if not job:
            return {"answer": f"I could not find job #{job_id}.", "citations": [], "uncertainty": "not_found"}
        return {
            "answer": f"Job #{job.id}: {job.title} at {job.company} ({job.state}).",
            "citations": _citations(("job", job.id)),
            "uncertainty": None,
        }

    if "company" in q:
        companies = db.query(Company).limit(5).all()
        if not companies:
            return {"answer": "No companies are registered yet.", "citations": [], "uncertainty": "empty"}
        names = ", ".join(c.canonical_name for c in companies)
        return {
            "answer": f"Registered companies include: {names}.",
            "citations": _citations(*(("company", c.id) for c in companies)),
            "uncertainty": "partial_list" if db.query(Company).count() > 5 else None,
        }

    if "interview" in q:
        packs = db.query(InterviewPack).limit(3).all()
        if not packs:
            return {"answer": "No interview packs have been generated yet.", "citations": [], "uncertainty": "empty"}
        summary = "; ".join(f"job #{p.job_id}" for p in packs)
        return {
            "answer": f"Interview packs exist for: {summary}.",
            "citations": _citations(*(("interview_pack", p.id) for p in packs)),
            "uncertainty": None,
        }

    if "recruiter" in q or "gmail" in q or "email" in q:
        signals = db.query(RecruiterSignal).order_by(RecruiterSignal.received_at.desc()).limit(5).all()
        if not signals:
            return {"answer": "No Gmail lifecycle signals synced yet.", "citations": [], "uncertainty": "empty"}
        types = ", ".join(s.signal_type for s in signals)
        return {
            "answer": f"Recent signal types: {types}.",
            "citations": _citations(*(("recruiter_signal", s.id) for s in signals)),
            "uncertainty": None,
        }

    return {
        "answer": (
            "I can answer questions about jobs, applications, companies, interviews, and Gmail signals. "
            "Try: 'How many jobs?' or 'Tell me about job #1'."
        ),
        "citations": [],
        "uncertainty": "needs_specific_question",
    }
