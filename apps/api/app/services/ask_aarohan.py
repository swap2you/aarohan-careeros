"""Ask Aarohan — context-aware Q&A grounded in CareerOS database records."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Application, Company, InterviewPack, Job, JobScore, RecruiterSignal, WorkflowState
from app.services.ai_budget import BudgetExceededError, enforce_budget, record_usage
from app.services.audit import write_audit

BLOCKED_SECRET_WORDS = ("secret", "password", "token", "oauth", "credential")
OFF_TOPIC_WORDS = (
    "stock",
    "crypto",
    "bitcoin",
    "weather",
    "politics",
    "recipe",
    "movie",
    "sports score",
    "nfl",
    "nba",
)


def _citations(*pairs: tuple[str, str | int]) -> list[dict]:
    return [{"type": t, "id": str(i)} for t, i in pairs]


def _blocked_policy(question: str) -> bool:
    q = question.lower()
    return any(word in q for word in BLOCKED_SECRET_WORDS)


def _is_off_topic(question: str) -> bool:
    q = question.lower()
    career_hints = (
        "job",
        "application",
        "company",
        "interview",
        "salary",
        "gmail",
        "recruiter",
        "packet",
        "approval",
        "shortlist",
        "career",
        "resume",
        "employer",
        "role",
        "pipeline",
        "aarohan",
    )
    if any(h in q for h in career_hints):
        return False
    return any(word in q for word in OFF_TOPIC_WORDS)


def _llm_url() -> str:
    if settings.ai_provider == "openrouter":
        return "https://openrouter.ai/api/v1/chat/completions"
    return "https://api.openai.com/v1/chat/completions"


def _snapshot_overview(db: Session) -> dict[str, Any]:
    return {
        "total_jobs": db.query(Job).count(),
        "shortlisted_jobs": db.query(Job).filter(Job.state == WorkflowState.SHORTLISTED.value).count(),
        "applications_ready": db.query(Application)
        .filter(Application.state == WorkflowState.PACKET_READY.value)
        .count(),
        "submitted_applications": db.query(Application)
        .filter(Application.state == WorkflowState.SUBMITTED.value)
        .count(),
        "companies": db.query(Company).count(),
        "interview_packs": db.query(InterviewPack).count(),
    }


def _snapshot_job(db: Session, job_id: int) -> dict[str, Any] | None:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        return None
    score = db.query(JobScore).filter(JobScore.job_id == job_id).one_or_none()
    app = db.query(Application).filter(Application.job_id == job_id).one_or_none()
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "state": job.state,
        "source": job.source,
        "location": job.location,
        "role_family": job.role_family,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "url": job.url,
        "score": {
            "total": score.total_score if score else None,
            "trust": score.trust_score if score else None,
            "hard_filter_passed": score.hard_filter_passed if score else None,
        },
        "application_state": app.state if app else None,
    }


def _snapshot_recent_jobs(db: Session, limit: int = 8) -> list[dict]:
    rows = db.query(Job).order_by(Job.discovered_at.desc()).limit(limit).all()
    return [
        {
            "id": j.id,
            "title": j.title[:120],
            "company": j.company,
            "state": j.state,
            "salary_max": j.salary_max,
        }
        for j in rows
    ]


def _salary_stats(db: Session) -> dict[str, Any]:
    rows = (
        db.query(func.avg(Job.salary_max), func.max(Job.salary_max), func.count(Job.id))
        .filter(Job.salary_max.isnot(None))
        .one()
    )
    avg_val, max_val, count = rows
    return {
        "jobs_with_salary": count or 0,
        "average_max_salary_usd": round(float(avg_val), 2) if avg_val else None,
        "highest_max_salary_usd": max_val,
    }


def _build_data_bundle(db: Session, context: dict | None, question: str) -> dict[str, Any]:
    ctx = context or {}
    bundle: dict[str, Any] = {
        "overview": _snapshot_overview(db),
        "salary_stats": _salary_stats(db),
        "page": ctx.get("page"),
    }
    job_id = ctx.get("job_id")
    if job_id:
        bundle["focused_job"] = _snapshot_job(db, int(job_id))
    elif match := re.search(r"job\s*#?\s*(\d+)", question, re.I):
        bundle["focused_job"] = _snapshot_job(db, int(match.group(1)))
    bundle["recent_jobs"] = _snapshot_recent_jobs(db)
    if "salary" in question.lower() or "pay" in question.lower():
        high = (
            db.query(Job)
            .filter(Job.salary_max.isnot(None))
            .order_by(Job.salary_max.desc())
            .limit(5)
            .all()
        )
        bundle["top_salary_jobs"] = [
            {"id": j.id, "title": j.title[:80], "company": j.company, "salary_max": j.salary_max}
            for j in high
        ]
    if any(w in question.lower() for w in ("gmail", "recruiter", "email", "signal")):
        signals = (
            db.query(RecruiterSignal).order_by(RecruiterSignal.received_at.desc()).limit(8).all()
        )
        bundle["recent_signals"] = [
            {"id": s.id, "type": s.signal_type, "sender": s.sender_email, "subject": (s.subject or "")[:100]}
            for s in signals
        ]
    return bundle


def _answer_with_llm(
    db: Session,
    question: str,
    bundle: dict[str, Any],
    *,
    actor: str,
    context: dict | None,
) -> dict:
    enforce_budget(db, estimated_cost=0.05, operation="ask_aarohan")
    system = (
        "You are Ask Aarohan, a read-only assistant for the CareerOS job search system. "
        "Answer ONLY using the JSON DATA provided. Never invent employers, salaries, or statuses. "
        "If the data is insufficient, say exactly what is missing. "
        "Decline off-topic questions (stocks, weather, general trivia). "
        "Keep answers concise (under 200 words) and cite record types when relevant."
    )
    user = f"DATA:\n{json.dumps(bundle, default=str)[:12000]}\n\nQUESTION:\n{question}"
    headers = {"Authorization": f"Bearer {settings.ai_api_key}", "Content-Type": "application/json"}
    if settings.ai_provider == "openrouter":
        headers["HTTP-Referer"] = "http://localhost:3000"
        headers["X-Title"] = "Aarohan CareerOS"
    model = settings.ask_aarohan_model or "gpt-4o-mini"
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            _llm_url(),
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": 600,
            },
        )
    if response.status_code != 200:
        raise RuntimeError(f"LLM request failed: {response.status_code}")
    body = response.json()
    answer = body["choices"][0]["message"]["content"].strip()
    usage = body.get("usage") or {}
    record_usage(
        db,
        operation="ask_aarohan",
        cost_usd=0.05,
        model=model,
        tokens_in=int(usage.get("prompt_tokens") or 0),
        tokens_out=int(usage.get("completion_tokens") or 0),
        job_id=(context or {}).get("job_id"),
        usage_kind="estimated",
    )
    write_audit(
        db,
        event_type="ask_aarohan.llm",
        actor=actor,
        resource_type="ask",
        details={"model": model, "page": (context or {}).get("page")},
    )
    cites = []
    if bundle.get("focused_job"):
        cites.append({"type": "job", "id": str(bundle["focused_job"]["id"])})
    cites.append({"type": "overview", "id": "snapshot"})
    return {
        "answer": answer,
        "citations": cites,
        "uncertainty": None,
        "mode": "ai_grounded",
    }


def _answer_with_data_engine(db: Session, question: str, bundle: dict[str, Any]) -> dict:
    q = question.strip().lower()
    overview = bundle["overview"]

    if "focused_job" in bundle:
        job = bundle["focused_job"]
        if not job:
            return {
                "answer": "I could not find that job in your database.",
                "citations": [],
                "uncertainty": "not_found",
                "mode": "database",
            }
        salary = "Not disclosed"
        if job.get("salary_min") or job.get("salary_max"):
            salary = f"${job.get('salary_min') or '?'} – ${job.get('salary_max') or '?'}"
        score = job.get("score") or {}
        return {
            "answer": (
                f"Job #{job['id']}: {job['title']} at {job['company']} ({job['state']}). "
                f"Salary: {salary}. Fit score: {score.get('total') or 'not scored'}. "
                f"Trust: {score.get('trust') or '—'}. "
                f"Application: {job.get('application_state') or 'none yet'}."
            ),
            "citations": _citations(("job", job["id"])),
            "uncertainty": None,
            "mode": "database",
        }

    if "salary" in q or "pay" in q or "compensation" in q:
        stats = bundle["salary_stats"]
        top = bundle.get("top_salary_jobs") or []
        if not stats["jobs_with_salary"]:
            return {
                "answer": "No jobs in your database have published salary ranges yet.",
                "citations": _citations(("jobs", "salary")),
                "uncertainty": "empty",
                "mode": "database",
            }
        top_line = ""
        if top:
            top_line = " Highest: " + "; ".join(
                f"#{j['id']} {j['company']} (${j['salary_max']:,})" for j in top[:3]
            )
        return {
            "answer": (
                f"{stats['jobs_with_salary']} jobs have salary data. "
                f"Average max: ${stats['average_max_salary_usd']:,.0f}. "
                f"Highest max: ${stats['highest_max_salary_usd']:,}.{top_line}"
            ),
            "citations": _citations(("jobs", "salary")),
            "uncertainty": None,
            "mode": "database",
        }

    if "how many jobs" in q or "total jobs" in q or "pipeline" in q:
        return {
            "answer": f"There are {overview['total_jobs']} jobs in the pipeline ({overview['shortlisted_jobs']} shortlisted).",
            "citations": _citations(("jobs", "collection")),
            "uncertainty": None,
            "mode": "database",
        }

    if "application" in q or "packet" in q or "attention" in q:
        return {
            "answer": (
                f"{overview['applications_ready']} applications are ready for review (PACKET_READY). "
                f"{overview['submitted_applications']} are marked submitted."
            ),
            "citations": _citations(("applications", "state")),
            "uncertainty": None,
            "mode": "database",
        }

    if "company" in q or "companies" in q:
        companies = db.query(Company).limit(8).all()
        if not companies:
            return {
                "answer": "No companies are registered in the ledger yet.",
                "citations": [],
                "uncertainty": "empty",
                "mode": "database",
            }
        names = ", ".join(c.canonical_name for c in companies)
        return {
            "answer": f"Registered companies ({overview['companies']} total) include: {names}.",
            "citations": _citations(*(("company", c.id) for c in companies)),
            "uncertainty": "partial_list" if overview["companies"] > len(companies) else None,
            "mode": "database",
        }

    if "interview" in q:
        packs = db.query(InterviewPack).limit(5).all()
        if not packs:
            return {
                "answer": "No interview packs have been generated yet.",
                "citations": [],
                "uncertainty": "empty",
                "mode": "database",
            }
        summary = ", ".join(f"job #{p.job_id}" for p in packs)
        return {
            "answer": f"Interview packs exist for: {summary}.",
            "citations": _citations(*(("interview_pack", p.id) for p in packs)),
            "uncertainty": None,
            "mode": "database",
        }

    if "gmail" in q or "recruiter" in q or "signal" in q:
        signals = bundle.get("recent_signals") or []
        if not signals:
            return {
                "answer": "No Gmail lifecycle signals are synced yet. Run Gmail sync from Settings.",
                "citations": [],
                "uncertainty": "empty",
                "mode": "database",
            }
        summary = "; ".join(f"{s['type']} from {s['sender']}" for s in signals[:5])
        return {
            "answer": f"Recent Gmail signals: {summary}.",
            "citations": _citations(*(("recruiter_signal", s["id"]) for s in signals[:5])),
            "uncertainty": None,
            "mode": "database",
        }

    recent = bundle.get("recent_jobs") or []
    if recent:
        sample = "; ".join(f"#{j['id']} {j['company']}" for j in recent[:4])
        return {
            "answer": (
                f"I can answer from your CareerOS data ({overview['total_jobs']} jobs). "
                f"Recent: {sample}. "
                "Try asking about salaries, a specific job #, applications ready, or Gmail signals. "
                "Configure AI_API_KEY for richer natural-language answers."
            ),
            "citations": _citations(*(("job", j["id"]) for j in recent[:4])),
            "uncertainty": "needs_specific_question",
            "mode": "database",
        }

    return {
        "answer": "Your CareerOS database is empty. Ingest jobs from Fresh Jobs first.",
        "citations": [],
        "uncertainty": "empty",
        "mode": "database",
    }


def answer_question(
    db: Session,
    question: str,
    *,
    actor: str,
    context: dict | None = None,
) -> dict:
    write_audit(
        db,
        event_type="ask_aarohan.query",
        actor=actor,
        resource_type="ask",
        resource_id="query",
        details={"question_length": len(question), "context": context or {}},
    )

    if _blocked_policy(question):
        return {
            "answer": "I cannot access or disclose authentication secrets or OAuth tokens.",
            "citations": [],
            "uncertainty": "blocked_policy",
            "mode": "policy",
        }

    if _is_off_topic(question):
        return {
            "answer": (
                "I only answer questions about your CareerOS data — jobs, applications, companies, "
                "interviews, salaries, and Gmail signals. I can't help with stocks or general topics."
            ),
            "citations": [],
            "uncertainty": "off_topic",
            "mode": "policy",
        }

    bundle = _build_data_bundle(db, context, question)

    if settings.ai_api_key:
        try:
            return _answer_with_llm(db, question, bundle, actor=actor, context=context)
        except BudgetExceededError as exc:
            fallback = _answer_with_data_engine(db, question, bundle)
            fallback["uncertainty"] = str(exc)
            fallback["mode"] = "database_budget_fallback"
            return fallback
        except Exception:
            pass

    return _answer_with_data_engine(db, question, bundle)
