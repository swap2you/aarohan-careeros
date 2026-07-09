"""Deterministic Fresh Jobs eligibility gates (geography, freshness, role, salary, URL)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.services.discovery_policy import freshness_max_age_hours, job_discovery_policy, salary_minimum_usd

# Reason codes (Workflow Lock 01)
STALE_OVER_48_HOURS = "STALE_OVER_48_HOURS"
TIMESTAMP_UNKNOWN = "TIMESTAMP_UNKNOWN"
FOREIGN_ONLY = "FOREIGN_ONLY"
REMOTE_ELIGIBILITY_AMBIGUOUS = "REMOTE_ELIGIBILITY_AMBIGUOUS"
RELOCATION_REQUIRED = "RELOCATION_REQUIRED"
ROLE_OUT_OF_SCOPE = "ROLE_OUT_OF_SCOPE"
COMPENSATION_BELOW_MINIMUM = "COMPENSATION_BELOW_MINIMUM"
MALFORMED_DIGEST = "MALFORMED_DIGEST"
SAVED_SEARCH_URL_NOT_JOB_URL = "SAVED_SEARCH_URL_NOT_JOB_URL"
COMPANY_UNKNOWN = "COMPANY_UNKNOWN"
DUPLICATE_PROVIDER_ID = "DUPLICATE_PROVIDER_ID"
DUPLICATE_CANONICAL_URL = "DUPLICATE_CANONICAL_URL"
DUPLICATE_FINGERPRINT = "DUPLICATE_FINGERPRINT"
CLOSED_POSTING = "CLOSED_POSTING"

ELIGIBLE_US = "ELIGIBLE_US"
ELIGIBLE_LOCAL = "ELIGIBLE_LOCAL"
AMBIGUOUS = "AMBIGUOUS"
INELIGIBLE_FOREIGN = "INELIGIBLE_FOREIGN"
RELOCATION_REQUIRED_LOC = "RELOCATION_REQUIRED"

DECISION_ACCEPT = "ACCEPT"
DECISION_SECONDARY = "SECONDARY_REVIEW"
DECISION_QUARANTINE = "QUARANTINE"
DECISION_REJECT = "REJECT"
DECISION_DUPLICATE = "DUPLICATE"

FOREIGN_MARKERS = (
    r"\bcanada\b",
    r"\bindia\b",
    r"\bbangalore\b",
    r"\bbengaluru\b",
    r"\bhyderabad\b",
    r"\bpune\b",
    r"\bfrance\b",
    r"\bparis\b",
    r"\beurope\b",
    r"\beuropean\b",
    r"\buk\b",
    r"\bunited kingdom\b",
    r"\blondon\b",
    r"\bapac\b",
    r"\baustralia\b",
    r"\bgermany\b",
    r"\bnetherlands\b",
    r"\bpoland\b",
    r"\bmexico\b",
    r"\bbrazil\b",
    r"\bphilippines\b",
    r"\bsingapore\b",
    r"\bjapan\b",
    r"\bemea\b",
)

US_MARKERS = (
    r"\bunited states\b",
    r"\bu\.?s\.?a\.?\b",
    r"\bu\.?s\.?\b",
    r"\bus-only\b",
    r"\bus based\b",
    r"\bus-based\b",
    r"\bremote[- ]us\b",
    r"\bremote \(us\)\b",
    r"\banywhere in the (us|u\.s\.|united states)\b",
)

US_STATE_MARKERS = (
    r"\balabama\b|\balaska\b|\barizona\b|\barkansas\b|\bcalifornia\b|\bcolorado\b|"
    r"\bconnecticut\b|\bdelaware\b|\bflorida\b|\bgeorgia\b|\bhawaii\b|\bidaho\b|"
    r"\billinois\b|\bindiana\b|\biowa\b|\bkansas\b|\bkentucky\b|\blouisiana\b|"
    r"\bmaine\b|\bmaryland\b|\bmassachusetts\b|\bmichigan\b|\bminnesota\b|"
    r"\bmississippi\b|\bmissouri\b|\bmontana\b|\bnebraska\b|\bnevada\b|"
    r"\bnew hampshire\b|\bnew jersey\b|\bnew mexico\b|\bnew york\b|"
    r"\bnorth carolina\b|\bnorth dakota\b|\bohio\b|\boklahoma\b|\boregon\b|"
    r"\bpennsylvania\b|\brhode island\b|\bsouth carolina\b|\bsouth dakota\b|"
    r"\btennessee\b|\btexas\b|\butah\b|\bvermont\b|\bvirginia\b|\bwashington\b|"
    r"\bwest virginia\b|\bwisconsin\b|\bwyoming\b|"
    r"\b,\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|"
    r"MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|"
    r"WA|WV|WI|WY)\b"
)

RELOCATION_MARKERS = (
    r"\brelocation required\b",
    r"\bmust relocate\b",
    r"\bmandatory relocation\b",
    r"\brelocate to\b",
    r"\bon[- ]?site only\b",
    r"\bno remote\b",
)

CLOSED_MARKERS = (
    r"\bno longer accepting applications\b",
    r"\bposition (has been )?filled\b",
    r"\bthis job is closed\b",
    r"\bapplications closed\b",
)


@dataclass
class EligibilityResult:
    decision: str
    reason_codes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    location_eligibility: str | None = None
    location_reason: str | None = None
    role_eligibility: str | None = None
    role_eligibility_reason: str | None = None
    recommended_profile: str | None = None
    profile_scores: dict[str, float] = field(default_factory=dict)
    matched_title_patterns: list[str] = field(default_factory=list)
    freshness_bucket: str | None = None
    freshness_source: str | None = None
    effective_freshness_at: datetime | None = None
    freshness_hours: float | None = None
    provider_posted_at: datetime | None = None
    source_received_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_codes": self.reason_codes,
            "reasons": self.reasons,
            "location_eligibility": self.location_eligibility,
            "location_reason": self.location_reason,
            "role_eligibility": self.role_eligibility,
            "role_eligibility_reason": self.role_eligibility_reason,
            "recommended_profile": self.recommended_profile,
            "profile_scores": self.profile_scores,
            "matched_title_patterns": self.matched_title_patterns,
            "freshness_bucket": self.freshness_bucket,
            "freshness_source": self.freshness_source,
            "effective_freshness_at": self.effective_freshness_at.isoformat()
            if self.effective_freshness_at
            else None,
            "freshness_hours": self.freshness_hours,
            "provider_posted_at": self.provider_posted_at.isoformat() if self.provider_posted_at else None,
            "source_received_at": self.source_received_at.isoformat() if self.source_received_at else None,
        }


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _text_blob(payload: dict) -> str:
    parts = [
        payload.get("title") or "",
        payload.get("company") or "",
        payload.get("location") or "",
        payload.get("workplace_type") or "",
        payload.get("description_text") or "",
    ]
    return " ".join(parts).lower()


def evaluate_location(payload: dict) -> tuple[str, str]:
    """Return (location_eligibility, reason)."""
    text = _text_blob(payload)
    location = (payload.get("location") or "").lower()
    workplace = (payload.get("workplace_type") or "").lower()
    policy = job_discovery_policy().get("geography", {})
    local_terms = [t.lower() for t in policy.get("local_hybrid", [])]

    if any(re.search(p, text) for p in RELOCATION_MARKERS):
        return RELOCATION_REQUIRED_LOC, "Posting requires relocation or onsite-only outside preference"

    foreign_hits = [p for p in FOREIGN_MARKERS if re.search(p, text)]
    us_hit = any(re.search(p, text) for p in US_MARKERS) or bool(re.search(US_STATE_MARKERS, text, re.I))
    local_hit = any(term in text for term in local_terms)

    # Explicit foreign-only without US eligibility
    if foreign_hits and not us_hit:
        return INELIGIBLE_FOREIGN, f"Foreign-only geography markers: {', '.join(foreign_hits[:3])}"

    if local_hit and ("hybrid" in text or "onsite" in text or "on-site" in text or "office" in text):
        return ELIGIBLE_LOCAL, "Local/hybrid Central Pennsylvania geography"

    if us_hit:
        return ELIGIBLE_US, "Explicit US eligibility or US location"

    if "remote" in text or "remote" in workplace or "remote" in location:
        # Worldwide remote only when US candidates explicitly eligible (already handled by us_hit)
        if re.search(r"\b(worldwide|global|anywhere)\b", text) and not us_hit:
            return AMBIGUOUS, "Worldwide/global remote without explicit US eligibility"
        return AMBIGUOUS, "Remote with no country/eligibility information"

    if location.strip() in {"", "n/a", "not specified", "unspecified"}:
        return AMBIGUOUS, "Location unspecified"

    # Non-remote location without US markers
    if location and not us_hit and not local_hit:
        return INELIGIBLE_FOREIGN, f"Non-US location without US eligibility: {location[:80]}"

    return AMBIGUOUS, "Geography could not be confirmed as US-eligible"


def evaluate_freshness(
    payload: dict,
    *,
    now: datetime | None = None,
    allow_discovered_at: bool = False,
) -> tuple[str | None, str | None, datetime | None, float | None, datetime | None, datetime | None, list[str], list[str]]:
    """
    Returns:
      freshness_bucket, freshness_source, effective_at, hours,
      provider_posted_at, source_received_at, reason_codes, reasons
    """
    now = now or datetime.utcnow()
    max_age = freshness_max_age_hours()
    new_hours = int(job_discovery_policy().get("freshness", {}).get("new_hours", 24))

    provider_posted_at = _parse_dt(payload.get("provider_posted_at") or payload.get("posted_at"))
    source_received_at = _parse_dt(payload.get("source_received_at") or payload.get("received_at"))
    discovered_at = _parse_dt(payload.get("discovered_at")) or now

    effective: datetime | None = None
    source: str | None = None
    if provider_posted_at:
        effective = provider_posted_at
        source = "provider_posted_at"
    elif source_received_at:
        effective = source_received_at
        source = "source_received_at"
    elif allow_discovered_at or payload.get("source") == "user_forwarded_links":
        effective = discovered_at
        source = "discovered_at"
    else:
        return None, None, None, None, provider_posted_at, source_received_at, [TIMESTAMP_UNKNOWN], [
            "Automated job has no reliable posted_at or source_received_at"
        ]

    hours = (now - effective).total_seconds() / 3600.0
    if hours < 0:
        hours = 0.0
    if hours > max_age:
        return (
            "STALE",
            source,
            effective,
            hours,
            provider_posted_at,
            source_received_at,
            [STALE_OVER_48_HOURS],
            [f"Effective age {hours:.1f}h exceeds Fresh Jobs max {max_age}h"],
        )
    bucket = "NEW" if hours <= new_hours else "RECENT"
    return bucket, source, effective, hours, provider_posted_at, source_received_at, [], []


def score_role_profiles(payload: dict) -> tuple[str | None, str | None, str | None, dict[str, float], list[str]]:
    """Return role_eligibility, reason, recommended_profile, profile_scores, matched_patterns."""
    title = (payload.get("title") or "").lower().strip()
    text = _text_blob(payload)
    profiles = job_discovery_policy().get("role_profiles", [])
    reject_patterns = [p.lower() for p in job_discovery_policy().get("role_reject_patterns", [])]

    scores: dict[str, float] = {}
    best_primary: tuple[float, str | None, list[str]] = (0.0, None, [])
    best_secondary: tuple[float, str | None, list[str]] = (0.0, None, [])

    for profile in profiles:
        pid = profile["id"]
        patterns = [p.lower() for p in profile.get("title_patterns", [])]
        hits = [p for p in patterns if p in title or p in text]
        score = 0.0
        if hits:
            title_hits = [p for p in hits if p in title]
            score = 40.0 + 15.0 * len(title_hits) + 5.0 * (len(hits) - len(title_hits))
            # Prefer longer title pattern matches (avoids "engineering manager" beating QE Manager)
            if title_hits:
                score += max(len(p) for p in title_hits) * 0.5
            require_any = [r.lower() for r in profile.get("require_any", [])]
            if require_any:
                if not any(r in text for r in require_any):
                    score = 0.0
                    hits = []
                else:
                    score += 10.0
        scores[pid] = score
        eligibility = profile.get("eligibility", "primary")
        if score <= 0:
            continue
        if eligibility == "secondary":
            if score > best_secondary[0]:
                best_secondary = (score, pid, hits)
        else:
            if score > best_primary[0]:
                best_primary = (score, pid, hits)

    if best_primary[1]:
        return (
            "primary",
            f"Matched primary profile: {best_primary[1]}",
            best_primary[1],
            scores,
            best_primary[2],
        )

    if best_secondary[1]:
        return (
            "secondary",
            f"Secondary-review profile: {best_secondary[1]}",
            best_secondary[1],
            scores,
            best_secondary[2],
        )

    for rp in reject_patterns:
        if rp in title:
            return "reject", f"Title matches out-of-scope pattern: {rp}", None, scores, []
    return "reject", "No target role profile matched", None, scores, []


def is_saved_search_url(url: str) -> bool:
    if not url:
        return True
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    qs = parse_qs(parsed.query)
    if "linkedin.com" in host:
        if "/jobs/view/" in path:
            return False
        if "/jobs/search" in path or "/jobs/collections" in path or "saved" in path:
            return True
        if not re.search(r"/jobs/view/\d+", path):
            return True
    if "indeed.com" in host:
        if "jk" in qs or "/viewjob" in path:
            return False
        if "/jobs" in path or "q=" in parsed.query:
            return True
    return False


def evaluate_eligibility(
    payload: dict,
    *,
    now: datetime | None = None,
    skip_freshness: bool = False,
    allow_discovered_at: bool = False,
) -> EligibilityResult:
    result = EligibilityResult(decision=DECISION_ACCEPT)
    text = _text_blob(payload)
    title = (payload.get("title") or "").strip()
    company = (payload.get("company") or "").strip()
    url = payload.get("url") or ""

    if any(re.search(p, text) for p in CLOSED_MARKERS):
        result.decision = DECISION_REJECT
        result.reason_codes.append(CLOSED_POSTING)
        result.reasons.append("Posting is closed or no longer accepting applications")
        return result

    if is_saved_search_url(url):
        result.decision = DECISION_REJECT
        result.reason_codes.append(SAVED_SEARCH_URL_NOT_JOB_URL)
        result.reasons.append("URL is a saved-search or listing page, not a job posting")
        return result

    bad_titles = {"linkedin job alert", "indeed job alert", "job alert", "linkedin role", "indeed role"}
    if title.lower() in bad_titles or not title or len(title) < 4:
        result.decision = DECISION_QUARANTINE
        result.reason_codes.append(MALFORMED_DIGEST)
        result.reasons.append("Title could not be extracted reliably from alert/digest")
        return result

    if company.lower() in {"unknown employer", "unknown company", "unknown", ""}:
        result.decision = DECISION_QUARANTINE
        result.reason_codes.append(COMPANY_UNKNOWN)
        result.reasons.append("Company/employer could not be extracted reliably")
        # Continue other gates but quarantine wins unless reject

    loc, loc_reason = evaluate_location(payload)
    result.location_eligibility = loc
    result.location_reason = loc_reason
    if loc == INELIGIBLE_FOREIGN:
        result.decision = DECISION_REJECT
        result.reason_codes.append(FOREIGN_ONLY)
        result.reasons.append(loc_reason)
        return result
    if loc == RELOCATION_REQUIRED_LOC:
        result.decision = DECISION_REJECT
        result.reason_codes.append(RELOCATION_REQUIRED)
        result.reasons.append(loc_reason)
        return result
    if loc == AMBIGUOUS:
        result.reason_codes.append(REMOTE_ELIGIBILITY_AMBIGUOUS)
        result.reasons.append(loc_reason)
        if result.decision == DECISION_ACCEPT:
            result.decision = DECISION_QUARANTINE

    if not skip_freshness:
        bucket, fsource, effective, hours, posted, received, codes, reasons = evaluate_freshness(
            payload, now=now, allow_discovered_at=allow_discovered_at
        )
        result.freshness_bucket = bucket
        result.freshness_source = fsource
        result.effective_freshness_at = effective
        result.freshness_hours = hours
        result.provider_posted_at = posted
        result.source_received_at = received
        if TIMESTAMP_UNKNOWN in codes:
            result.reason_codes.extend(codes)
            result.reasons.extend(reasons)
            if result.decision == DECISION_ACCEPT:
                result.decision = DECISION_QUARANTINE
        elif STALE_OVER_48_HOURS in codes:
            result.decision = DECISION_REJECT
            result.reason_codes.extend(codes)
            result.reasons.extend(reasons)
            return result

    role_elig, role_reason, recommended, scores, matched = score_role_profiles(payload)
    result.role_eligibility = role_elig
    result.role_eligibility_reason = role_reason
    result.recommended_profile = recommended
    result.profile_scores = scores
    result.matched_title_patterns = matched
    if role_elig == "reject":
        result.decision = DECISION_REJECT
        result.reason_codes.append(ROLE_OUT_OF_SCOPE)
        result.reasons.append(role_reason)
        return result
    if role_elig == "secondary" and result.decision == DECISION_ACCEPT:
        result.decision = DECISION_SECONDARY
        result.reasons.append(role_reason)

    salary_max = payload.get("salary_max")
    salary_min = payload.get("salary_min")
    published = salary_max or salary_min
    minimum = salary_minimum_usd()
    if published is not None and int(published) < minimum:
        result.decision = DECISION_REJECT
        result.reason_codes.append(COMPENSATION_BELOW_MINIMUM)
        result.reasons.append(f"Published compensation ${published} below minimum ${minimum}")
        return result

    if COMPANY_UNKNOWN in result.reason_codes and result.decision == DECISION_ACCEPT:
        result.decision = DECISION_QUARANTINE

    return result
