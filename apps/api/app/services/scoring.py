from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import EvidenceItem, Job, JobScore
from app.services.config_loader import candidate_profile, scoring_rubric
from app.services.normalization import detect_workplace_type


LEADERSHIP_KEYWORDS = [
    "director",
    "head of",
    "manager",
    "lead",
    "architect",
    "principal",
    "transformation",
]
TECH_KEYWORDS = [
    "quality",
    "test",
    "automation",
    "sdet",
    "performance",
    "ci/cd",
    "api",
    "selenium",
    "jmeter",
    "platform",
]
AI_KEYWORDS = [
    "genai",
    "llm",
    "agent",
    "ai-enabled",
    "prompt",
    "rag",
    "mcp",
]


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _keyword_score(text: str, keywords: list[str]) -> float:
    lowered = text.lower()
    hits = sum(1 for keyword in keywords if keyword in lowered)
    return _clamp((hits / max(len(keywords), 1)) * 100)


def score_job(db: Session, job: Job) -> JobScore:
    rubric = scoring_rubric()
    weights = rubric.get("weights", {})
    thresholds = rubric.get("thresholds", {})
    salary_policy = rubric.get("salary_policy", {})
    location_policy = rubric.get("location_policy", {})
    risk_policy = rubric.get("risk_policy", {})

    text = f"{job.title} {job.description_text} {job.location or ''}"
    workplace = job.workplace_type or detect_workplace_type(text)

    compensation_score = 50.0
    if job.salary_max:
        target = salary_policy.get("target_base_usd", 200000)
        reject_below = salary_policy.get("reject_if_published_max_below_usd", 170000)
        if job.salary_max < reject_below:
            compensation_score = 10.0
        elif job.salary_max >= target:
            compensation_score = 100.0
        else:
            compensation_score = _clamp((job.salary_max / target) * 100)
    elif salary_policy.get("keep_unknown_salary_if_scope_supports_target", True):
        compensation_score = 55.0

    remote_score = 20.0
    if workplace == "fully_remote_us":
        remote_score = 100.0
    elif workplace == "remote":
        remote_score = 85.0
    elif workplace == "hybrid":
        remote_score = 45.0
    elif workplace == "mandatory_relocation":
        remote_score = 0.0

    technical_fit_score = _keyword_score(text, TECH_KEYWORDS)
    leadership_score = _keyword_score(text, LEADERSHIP_KEYWORDS)
    ai_alignment_score = _keyword_score(text, AI_KEYWORDS)

    stability_score = 70.0
    if risk_policy.get("penalize_unstable_company") and any(
        token in text.lower() for token in ["stealth", "pre-seed", "contract only"]
    ):
        stability_score = 35.0

    public_evidence = db.query(EvidenceItem).filter(EvidenceItem.public_use.is_(True)).count()
    evidence_score = _clamp(min(public_evidence, 5) * 20)

    if risk_policy.get("penalize_title_without_scope") and leadership_score > 70 and technical_fit_score < 40:
        leadership_score *= 0.7

    total = (
        compensation_score * weights.get("compensation_and_benefits", 25) / 100
        + remote_score * weights.get("remote_and_location", 20) / 100
        + technical_fit_score * weights.get("core_technical_fit", 20) / 100
        + leadership_score * weights.get("leadership_scope", 10) / 100
        + ai_alignment_score * weights.get("ai_enabled_qe_alignment", 10) / 100
        + stability_score * weights.get("stability_and_company_quality", 10) / 100
        + evidence_score * weights.get("evidence_strength", 5) / 100
    )

    # Fit scoring produces a RANKING recommendation only. It must never mutate the
    # lifecycle `state` field: eligibility (eligible_for_owner + ingest_decision) is the
    # sole owner-visibility source of truth, and `state` is the application workflow
    # lifecycle. Overloading `state` with a fit-derived REJECT hid eligible jobs from
    # Fresh Jobs (Workflow Lock 01 stale-state defect). Recommendation is persisted on
    # JobScore.recommendation below.
    if total < thresholds.get("reject_below", 65):
        recommendation = "REJECT"
    elif total < thresholds.get("shortlist_min", 75):
        recommendation = "SECONDARY_REVIEW"
    elif total < thresholds.get("high_priority_min", 85):
        recommendation = "SHORTLIST"
    else:
        recommendation = "HIGH_PRIORITY"

    if job.freshness_hours and job.freshness_hours > candidate_profile().get("candidate", {}).get(
        "freshness_fallback_hours", 72
    ):
        total *= 0.95

    score = job.score or JobScore(job_id=job.id)
    score.total_score = round(total, 2)
    score.compensation_score = round(compensation_score, 2)
    score.remote_score = round(remote_score, 2)
    score.technical_fit_score = round(technical_fit_score, 2)
    score.leadership_score = round(leadership_score, 2)
    score.ai_alignment_score = round(ai_alignment_score, 2)
    score.stability_score = round(stability_score, 2)
    score.evidence_score = round(evidence_score, 2)
    score.fit_analysis = (
        f"Role aligns with QE leadership campaign. Workplace={workplace}. "
        f"Technical fit={technical_fit_score:.0f}, leadership={leadership_score:.0f}."
    )
    score.gap_analysis = "Review evidence registry for any TODO_VERIFY items before packet generation."
    score.stability_analysis = f"Stability score={stability_score:.0f}."
    score.recommendation = recommendation
    score.scored_at = datetime.utcnow()

    from app.services.trust_matching import analyze_job, apply_analysis_to_models

    analysis = analyze_job(db, job, score)
    apply_analysis_to_models(job, score, analysis)
    score.fit_analysis = analysis.match_summary

    db.add(score)
    db.add(job)
    db.commit()
    db.refresh(score)
    return score
