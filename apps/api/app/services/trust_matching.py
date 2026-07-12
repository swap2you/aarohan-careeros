"""Trust, matching, explainability, and hard filters."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Company, Job, JobScore
from app.services.config_loader import candidate_profile
from app.services.normalization import detect_workplace_type

VERIFIED_SOURCES = {
    "greenhouse_public_get",
    "lever_public_get",
    "ashby_public_get",
    "remotive_public_get",
    "remote_ok_public_get",
    "usajobs_api",
    "adzuna_api",
    "approved_remote_feeds",
}

ROLE_FAMILIES = {
    "tpm_delivery": [
        "technical project manager",
        "technical program manager",
        "engineering program manager",
        "delivery manager",
        "platform program manager",
    ],
    "qe_manager": [
        "quality engineering manager",
        "qe manager",
        "test engineering manager",
        "senior manager quality",
    ],
    "qe_leadership": [
        "director of quality",
        "head of quality",
        "vp quality",
        "quality engineering director",
    ],
    "platform_architect": [
        "platform architect",
        "test platform",
        "automation architect",
        "principal quality",
        "staff quality",
        "sdet architect",
    ],
    "ai_enabled_qe": [
        "ai-enabled",
        "genai",
        "llm quality",
        "agentic",
        "ai quality",
        "senior ai engineer",
    ],
}

DEFAULT_EXPIRY_DAYS = 60
STALE_POSTING_DAYS = 90


@dataclass
class MatchAnalysis:
    role_family: str
    trust_score: float
    trust_reasons: list[str] = field(default_factory=list)
    fit_reasons: list[str] = field(default_factory=list)
    hard_filter_passed: bool = True
    hard_filter_reasons: list[str] = field(default_factory=list)
    source_verified: bool = False
    expires_at: datetime | None = None
    is_expired: bool = False
    match_summary: str = ""
    match_card: dict = field(default_factory=dict)
    duplicate_source_note: str | None = None

    def to_dict(self) -> dict:
        return {
            "role_family": self.role_family,
            "trust_score": self.trust_score,
            "trust_reasons": self.trust_reasons,
            "fit_reasons": self.fit_reasons,
            "hard_filter_passed": self.hard_filter_passed,
            "hard_filter_reasons": self.hard_filter_reasons,
            "source_verified": self.source_verified,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired,
            "match_summary": self.match_summary,
            "match_card": self.match_card,
            "duplicate_source_note": self.duplicate_source_note,
        }


def get_preferences() -> dict:
    profile = candidate_profile()
    candidate = profile.get("candidate", {})
    positioning = profile.get("positioning", {})
    return {
        "target_base_salary_usd": candidate.get("target_base_salary_usd", 200000),
        "minimum_base_usd": candidate.get("secondary_compensation_rule", {}).get(
            "minimum_base_usd", 180000
        ),
        "remote_first": candidate.get("remote_first", True),
        "relocation_now": candidate.get("relocation_now", False),
        "home_base": candidate.get("home_base"),
        "work_authorization": candidate.get("work_authorization_public_statement"),
        "primary_roles": positioning.get("primary", []),
        "secondary_roles": positioning.get("secondary", []),
        "freshness_preferred_hours": candidate.get("freshness_preferred_hours", 24),
    }


def classify_role_family(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    for family, patterns in ROLE_FAMILIES.items():
        if any(pattern in text for pattern in patterns):
            return family
    if any(k in text for k in ["quality", "qe", "sdet", "test"]):
        return "qe_general"
    return "other"


def _compute_expiration(job: Job) -> tuple[datetime | None, bool]:
    base = job.posted_at or job.discovered_at
    if not base:
        return None, False
    expires = base + timedelta(days=DEFAULT_EXPIRY_DAYS)
    now = datetime.utcnow()
    is_expired = now > expires or (
        job.posted_at is not None and (now - job.posted_at).days > STALE_POSTING_DAYS
    )
    return expires, is_expired


def apply_hard_filters(job: Job, prefs: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    text = f"{job.title} {job.description_text} {job.location or ''}".lower()
    workplace = job.workplace_type or detect_workplace_type(text)

    if not prefs.get("relocation_now") and workplace == "mandatory_relocation":
        reasons.append("Hard filter: mandatory relocation while relocation is disabled in profile")

    if job.salary_max and job.salary_max < prefs.get("minimum_base_usd", 180000):
        reasons.append(
            f"Hard filter: published max salary ${job.salary_max:,} below minimum "
            f"${prefs.get('minimum_base_usd', 180000):,}"
        )

    if re.search(r"\b(no sponsorship|must be authorized to work in the u\.?s\.? only)\b", text):
        if prefs.get("work_authorization") == "TODO_VERIFY":
            reasons.append("Hard filter: work authorization requirement unclear — verify profile")

    if re.search(r"\b(75% travel|100% travel|extensive travel required)\b", text):
        reasons.append("Hard filter: travel requirement exceeds limited-travel preference")

    if re.search(r"\b(on-?site only|no remote)\b", text) and prefs.get("remote_first"):
        reasons.append("Hard filter: on-site only conflicts with remote-first preference")

    return len(reasons) == 0, reasons


def compute_trust_score(job: Job, db: Session, prefs: dict) -> tuple[float, list[str], bool]:
    reasons: list[str] = []
    score = 40.0
    verified = job.source in VERIFIED_SOURCES
    if verified:
        score += 25.0
        reasons.append(f"Verified automated source: {job.source}")
    else:
        reasons.append(f"Unverified or manual source: {job.source}")

    if job.company_id:
        company = db.query(Company).filter(Company.id == job.company_id).one_or_none()
        if company:
            score += 15.0
            reasons.append(f"Employer linked in company registry: {company.canonical_name}")

    if job.ats_job_id or job.requisition_id:
        score += 10.0
        reasons.append("ATS or requisition identifier present")

    if job.salary_min or job.salary_max:
        score += 10.0
        reasons.append("Compensation range published")

    if job.freshness_hours is not None and job.freshness_hours <= prefs.get("freshness_preferred_hours", 24):
        score += 10.0
        reasons.append("Posting within preferred freshness window")

    return min(100.0, score), reasons, verified


def build_fit_reasons(job: Job, score: JobScore, prefs: dict) -> list[str]:
    reasons: list[str] = []
    if score.technical_fit_score >= 60:
        reasons.append(f"Strong technical fit ({score.technical_fit_score:.0f}/100)")
    if score.leadership_score >= 60:
        reasons.append(f"Leadership scope alignment ({score.leadership_score:.0f}/100)")
    if score.remote_score >= 80:
        reasons.append("Remote or US-remote friendly arrangement")
    if score.compensation_score >= 70:
        reasons.append("Compensation aligns with target base")
    family = classify_role_family(job.title, job.description_text)
    primary = [r.lower() for r in prefs.get("primary_roles", [])]
    if any(token in job.title.lower() for token in primary):
        reasons.append("Title matches primary target role family")
    elif family != "other":
        reasons.append(f"Classified as role family: {family}")
    if score.ai_alignment_score >= 50:
        reasons.append(f"AI-enabled QE alignment ({score.ai_alignment_score:.0f}/100)")
    if not reasons:
        reasons.append("Review recommended — mixed alignment signals")
    return reasons


def duplicate_source_note(db: Session, job: Job) -> str | None:
    others = (
        db.query(Job)
        .filter(Job.dedupe_key == job.dedupe_key, Job.id != job.id)
        .order_by(Job.discovered_at.asc())
        .all()
    )
    if not others:
        return None
    sources = sorted({o.source for o in others} | {job.source})
    return f"Same role seen via {', '.join(sources)}; canonical record job #{others[0].id}"


def build_match_card(job: Job, analysis: MatchAnalysis, score: JobScore) -> dict:
    workplace = job.workplace_type or detect_workplace_type(job.description_text)
    salary = "Not published"
    if job.salary_min or job.salary_max:
        lo = job.salary_min or job.salary_max
        hi = job.salary_max or job.salary_min
        salary = f"${lo:,} – ${hi:,} {job.salary_currency}"

    return {
        "headline": f"{job.title} at {job.company}",
        "fit_score": score.total_score,
        "trust_score": analysis.trust_score,
        "recommendation": score.recommendation,
        "role_family": analysis.role_family,
        "workplace": workplace,
        "location": job.location,
        "compensation": salary,
        "freshness_hours": job.freshness_hours,
        "hard_filter": "PASS" if analysis.hard_filter_passed else "FAIL",
        "trust_highlights": analysis.trust_reasons[:3],
        "fit_highlights": analysis.fit_reasons[:4],
        "expired": analysis.is_expired,
        "source": job.source,
        "apply_url": job.url,
    }


def analyze_job(db: Session, job: Job, score: JobScore) -> MatchAnalysis:
    prefs = get_preferences()
    role_family = classify_role_family(job.title, job.description_text)
    hard_passed, hard_reasons = apply_hard_filters(job, prefs)
    trust_score, trust_reasons, source_verified = compute_trust_score(job, db, prefs)
    fit_reasons = build_fit_reasons(job, score, prefs)
    expires_at, is_expired = _compute_expiration(job)
    dup_note = duplicate_source_note(db, job)

    if is_expired:
        hard_passed = False
        hard_reasons.append("Hard filter: posting appears stale or expired")

    if dup_note:
        trust_reasons.append(dup_note)

    summary_parts = [
        f"Role family: {role_family}.",
        f"Trust {trust_score:.0f}/100, fit {score.total_score:.0f}/100.",
    ]
    if not hard_passed:
        summary_parts.append("Hard filters failed — review before proceeding.")
    elif score.recommendation in {"HIGH_PRIORITY", "SHORTLIST"}:
        summary_parts.append("Good match for current campaign.")
    match_summary = " ".join(summary_parts)

    analysis = MatchAnalysis(
        role_family=role_family,
        trust_score=trust_score,
        trust_reasons=trust_reasons,
        fit_reasons=fit_reasons,
        hard_filter_passed=hard_passed,
        hard_filter_reasons=hard_reasons,
        source_verified=source_verified,
        expires_at=expires_at,
        is_expired=is_expired,
        match_summary=match_summary,
        duplicate_source_note=dup_note,
    )
    analysis.match_card = build_match_card(job, analysis, score)
    return analysis


def apply_analysis_to_models(job: Job, score: JobScore, analysis: MatchAnalysis) -> None:
    job.role_family = analysis.role_family
    job.expires_at = analysis.expires_at
    job.is_expired = analysis.is_expired
    job.source_verified = analysis.source_verified
    job.match_summary = analysis.match_summary

    score.trust_score = round(analysis.trust_score, 2)
    score.trust_reasons = analysis.trust_reasons
    score.fit_reasons = analysis.fit_reasons
    score.hard_filter_passed = analysis.hard_filter_passed
    score.hard_filter_reasons = analysis.hard_filter_reasons
    score.match_card = analysis.match_card

    # A failed trust hard-filter is an advisory RANKING signal (recorded on the score),
    # never a lifecycle transition. It must not mutate `state`: doing so overloaded the
    # workflow lifecycle with a fit/trust rejection and hid owner-eligible jobs from
    # Fresh Jobs. Eligibility (eligible_for_owner + ingest_decision) remains the sole
    # owner-visibility gate; salary/fit stay ranking/review, not hard rejection.
    if not analysis.hard_filter_passed:
        score.recommendation = "REJECT"
