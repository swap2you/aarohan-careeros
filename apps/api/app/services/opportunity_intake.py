"""Ad hoc opportunity intake — extract, review, and confirm before job creation."""

from __future__ import annotations

import hashlib
import re
from html import unescape

from sqlalchemy.orm import Session

from app.services.ingestion import ingest_job
from app.services.normalization import detect_workplace_type, parse_salary_range
from app.services.provenance import PROVENANCE_MANUAL
from app.services.resume_builder import load_resume_profile
from app.services.sanitize import sanitize_html
from app.services.scoring import score_job

PROFILE_KEYWORDS: dict[str, list[str]] = {
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
    "director_qe": [
        "director of quality",
        "head of quality engineering",
        "qe transformation",
    ],
    "platform_architect": [
        "principal quality",
        "staff quality",
        "test automation architect",
        "qe architect",
        "platform architect",
    ],
    "ai_enabled_qe": [
        "ai quality",
        "llm evaluation",
        "agentic",
        "genai quality",
    ],
    "qe_leadership": [
        "quality engineering lead",
        "qe lead",
        "quality leader",
    ],
}

SOURCE_FROM_URL: list[tuple[str, str]] = [
    ("linkedin.com", "linkedin"),
    ("indeed.com", "indeed"),
    ("dice.com", "dice"),
    ("glassdoor.com", "glassdoor"),
    ("usajobs.gov", "usajobs"),
    ("greenhouse.io", "greenhouse"),
    ("lever.co", "lever"),
    ("ashbyhq.com", "ashby"),
    ("jobs.lever.co", "lever"),
    ("boards.greenhouse.io", "greenhouse"),
    ("adzuna", "adzuna"),
    ("jooble", "jooble"),
    ("remotive", "remotive"),
    ("remoteok", "remote_ok"),
]


def _detect_source(url: str | None) -> str:
    if not url:
        return "manual"
    lowered = url.lower()
    for needle, label in SOURCE_FROM_URL:
        if needle in lowered:
            return label
    return "manual"


def _strip_html(value: str) -> str:
    text = sanitize_html(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _first_match(pattern: str, text: str, flags: int = re.I) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def parse_job_fields(
    *,
    text: str,
    url: str | None = None,
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
    salary_text: str | None = None,
    requisition_id: str | None = None,
) -> dict:
    body = (text or "").strip()
    parsed_title = (title or "").strip() or _first_match(r"(?:title|position|role)\s*[:\-]\s*(.+)", body)
    parsed_company = (company or "").strip() or _first_match(r"(?:company|employer|organization)\s*[:\-]\s*(.+)", body)
    parsed_location = (location or "").strip() or _first_match(r"(?:location|where)\s*[:\-]\s*(.+)", body)
    parsed_salary = (salary_text or "").strip() or _first_match(
        r"(?:salary|compensation|pay)\s*[:\-]\s*(\$[\d,k\-\s]+(?:/year|/yr| per year)?)",
        body,
    )
    parsed_req = (requisition_id or "").strip() or _first_match(
        r"(?:requisition|req(?:uisition)?\.?|job)\s*(?:id|#)?\s*[:\-#]?\s*([A-Za-z0-9\-]+)",
        body,
    )
    if not parsed_title and body:
        for line in body.splitlines():
            clean = line.strip()
            if 8 <= len(clean) <= 120:
                parsed_title = clean
                break
    if not parsed_company:
        parsed_company = "Unknown Company"
    if not parsed_title:
        parsed_title = "Untitled Role"

    salary_min, salary_max = parse_salary_range(parsed_salary or body)
    workplace = detect_workplace_type(body)
    official_url = (url or "").strip()
    source = _detect_source(official_url)
    external_id = official_url or hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]

    return {
        "source": source if source != "manual" else "ad_hoc",
        "external_id": external_id,
        "title": parsed_title[:512],
        "company": parsed_company[:255],
        "url": official_url or f"adhoc://{external_id}",
        "location": parsed_location,
        "workplace_type": workplace,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_text": parsed_salary,
        "description_text": body[:50000],
        "description_html": "",
        "requisition_id": parsed_req,
        "posted_at": None,
    }


def recommend_profiles(title: str, description: str) -> list[dict]:
    """Recommend resume profiles using the same normalized title matching as eligibility."""
    from app.services.job_eligibility import score_role_profiles

    role_elig, role_reason, recommended, scores, matched, _norm = score_role_profiles(
        {"title": title or "", "description_text": description or ""}
    )
    ranked: list[tuple[float, str]] = []
    if recommended and scores.get(recommended, 0) > 0:
        ranked.append((scores[recommended], recommended))
    for pid, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        if score > 0 and pid != recommended:
            ranked.append((score, pid))
    # Fallback keyword scan for qe_leadership-style profiles not in discovery policy
    if not ranked:
        from app.services.title_normalization import pattern_in_title

        for profile_id, keywords in PROFILE_KEYWORDS.items():
            score = sum(2 for kw in keywords if pattern_in_title(kw, title or ""))
            if score:
                ranked.append((float(score), profile_id))
    if not ranked:
        ranked = [(1.0, "qe_leadership")]

    results: list[dict] = []
    for score, profile_id in ranked[:3]:
        try:
            profile = load_resume_profile(profile_id)
            reason = role_reason if profile_id == recommended else f"Matched normalized title for {profile.get('name', profile_id)}."
            if matched and profile_id == recommended:
                reason = f"Matched title pattern(s): {', '.join(matched[:3])}"
        except ValueError:
            profile = {"id": profile_id, "name": profile_id}
            reason = "Default profile recommendation."
        results.append(
            {
                "profile_id": profile_id,
                "profile_name": profile.get("name", profile_id),
                "reason": reason,
                "score": score,
                "role_eligibility": role_elig,
            }
        )
    return results


def extract_opportunity(
    *,
    url: str | None = None,
    plain_text: str | None = None,
    rich_text: str | None = None,
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
    salary_text: str | None = None,
    requisition_id: str | None = None,
    recruiter_email_text: str | None = None,
) -> dict:
    chunks = [plain_text or "", _strip_html(rich_text or ""), recruiter_email_text or ""]
    if url and not any(chunks):
        chunks.append(f"Forwarded job URL: {url}\nReview and paste the job description before confirming.")
    body = "\n\n".join(part for part in chunks if part.strip())
    fields = parse_job_fields(
        text=body,
        url=url,
        company=company,
        title=title,
        location=location,
        salary_text=salary_text,
        requisition_id=requisition_id,
    )
    recommendations = recommend_profiles(fields["title"], fields["description_text"])
    return {
        "extracted": fields,
        "editable_text": fields["description_text"],
        "recommended_profiles": recommendations,
        "requires_confirmation": True,
        "warnings": [
            "Review extracted company, title, and description before creating a job record.",
            "Uploaded screenshots/PDFs must be pasted or corrected manually until OCR is enabled.",
        ],
    }


def confirm_opportunity(
    db: Session,
    *,
    fields: dict,
    actor: str,
    resume_profile: str | None = None,
    generate_packet: bool = False,
) -> dict:
    payload = dict(fields)
    payload["data_provenance"] = PROVENANCE_MANUAL
    payload["owner_confirmed"] = True
    payload["manual_confirmed"] = True
    if not payload.get("source"):
        payload["source"] = "manual_opportunity"
    if not payload.get("external_id"):
        payload["external_id"] = payload.get("url") or payload.get("title") or "manual"
    if not payload.get("description_text"):
        raise ValueError("Description text is required after owner review.")
    job = ingest_job(db, payload, actor=actor, allow_discovered_at=True)
    # Classify as an owner-added, freshness-protected manual opportunity (Workflow 01.5 §8).
    from app.services.discovery_origin import mark_owner_added

    mark_owner_added(job, added_by=actor)
    db.commit()
    score_job(db, job)
    result: dict = {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "state": job.state,
        "origin": job.origin,
        "manual_status": job.manual_status,
    }
    if generate_packet and resume_profile:
        from app.services.documents import generate_application_packet

        application = generate_application_packet(db, job, actor=actor, resume_profile=resume_profile)
        result["application_id"] = application.id
        result["state"] = application.state
    return result
