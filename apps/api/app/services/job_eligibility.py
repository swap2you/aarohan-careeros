"""Deterministic Fresh Jobs eligibility gates (shared by ingest + audit)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.services.discovery_policy import job_discovery_policy
from app.services.sanitize import html_to_text
from app.services.title_normalization import normalize_title, pattern_in_title, title_tokens

# Reason codes
STALE_HISTORICAL = "STALE_HISTORICAL"
TIMESTAMP_UNKNOWN = "TIMESTAMP_UNKNOWN"
FRESHNESS_FALLBACK_USED = "FRESHNESS_FALLBACK_USED"
FOREIGN_ONLY = "FOREIGN_ONLY"
REMOTE_ELIGIBILITY_AMBIGUOUS = "REMOTE_ELIGIBILITY_AMBIGUOUS"
RELOCATION_REQUIRED = "RELOCATION_REQUIRED"
ROLE_OUT_OF_SCOPE = "ROLE_OUT_OF_SCOPE"
COMPENSATION_REVIEW = "COMPENSATION_REVIEW"
MALFORMED_DIGEST = "MALFORMED_DIGEST"
SAVED_SEARCH_URL_NOT_JOB_URL = "SAVED_SEARCH_URL_NOT_JOB_URL"
COMPANY_UNKNOWN = "COMPANY_UNKNOWN"
DUPLICATE_PROVIDER_ID = "DUPLICATE_PROVIDER_ID"
DUPLICATE_CANONICAL_URL = "DUPLICATE_CANONICAL_URL"
DUPLICATE_FINGERPRINT = "DUPLICATE_FINGERPRINT"
CLOSED_POSTING = "CLOSED_POSTING"
OWNER_REVIEW = "OWNER_REVIEW"

# Legacy alias kept for older tests/messages
STALE_OVER_48_HOURS = STALE_HISTORICAL
COMPENSATION_BELOW_MINIMUM = COMPENSATION_REVIEW

ELIGIBLE_US = "ELIGIBLE_US"
ELIGIBLE_LOCAL = "ELIGIBLE_LOCAL"
AMBIGUOUS = "AMBIGUOUS"
INELIGIBLE_FOREIGN = "INELIGIBLE_FOREIGN"
RELOCATION_REQUIRED_LOC = "RELOCATION_REQUIRED"

DECISION_ACCEPT = "ACCEPT"
DECISION_SECONDARY = "SECONDARY_REVIEW"
DECISION_QUARANTINE = "QUARANTINE"
DECISION_OWNER_REVIEW = "OWNER_REVIEW"
DECISION_REJECT = "REJECT"
DECISION_DUPLICATE = "DUPLICATE"
DECISION_HISTORICAL = "HISTORICAL"

TIER_TODAY = "TODAY"
TIER_FRESH = "FRESH"
TIER_RECENT = "RECENT"
TIER_HISTORICAL = "HISTORICAL"

SALARY_TARGET = "TARGET"
SALARY_STRONG = "STRONG"
SALARY_REVIEW = "REVIEW"
SALARY_UNKNOWN = "UNKNOWN"

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
    r"\bnordics?\b",
    r"\bscandinavia\b",
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

US_STATE_NAMES = (
    r"\balabama\b|\balaska\b|\barizona\b|\barkansas\b|\bcalifornia\b|\bcolorado\b|"
    r"\bconnecticut\b|\bdelaware\b|\bflorida\b|\bgeorgia\b|\bhawaii\b|\bidaho\b|"
    r"\billinois\b|\bindiana\b|\biowa\b|\bkansas\b|\bkentucky\b|\blouisiana\b|"
    r"\bmaine\b|\bmaryland\b|\bmassachusetts\b|\bmichigan\b|\bminnesota\b|"
    r"\bmississippi\b|\bmissouri\b|\bmontana\b|\bnebraska\b|\bnevada\b|"
    r"\bnew hampshire\b|\bnew jersey\b|\bnew mexico\b|\bnew york\b|"
    r"\bnorth carolina\b|\bnorth dakota\b|\bohio\b|\boklahoma\b|\boregon\b|"
    r"\bpennsylvania\b|\brhode island\b|\bsouth carolina\b|\bsouth dakota\b|"
    r"\btennessee\b|\btexas\b|\butah\b|\bvermont\b|\bvirginia\b|\bwashington\b|"
    r"\bwest virginia\b|\bwisconsin\b|\bwyoming\b|\bdistrict of columbia\b"
)

US_STATE_ABBREV = re.compile(
    r"(?:^|[\s,])(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|"
    r"MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|"
    r"WA|WV|WI|WY|DC)(?:$|[\s,.])",
    re.I,
)

US_CITY_HINTS = {
    "atlanta",
    "northford",
    "harrisburg",
    "new york",
    "san francisco",
    "seattle",
    "austin",
    "boston",
    "chicago",
    "denver",
    "dallas",
    "houston",
    "miami",
    "phoenix",
    "portland",
    "philadelphia",
    "pittsburgh",
    "washington",
    "arlington",
    "alexandria",
    "reston",
    "raleigh",
    "charlotte",
    "tampa",
    "orlando",
    "minneapolis",
    "detroit",
    "columbus",
    "indianapolis",
    "nashville",
    "salt lake",
    "san diego",
    "los angeles",
    "san jose",
    "sacramento",
}

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

PROTECTED_STATES = {
    "SHORTLISTED",
    "PACKET_READY",
    "PACKET_GENERATING",
    "NEEDS_EDIT",
    "APPROVED_FOR_SUBMISSION",
    "SUBMITTED",
    "FOLLOW_UP_DUE",
    "RECRUITER_SIGNAL",
    "INTERVIEW_SIGNAL",
    "INTERVIEW_SCHEDULED",
    "OFFER",
}


@dataclass
class EligibilityResult:
    decision: str
    reason_codes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    location_eligibility: str | None = None
    location_reason: str | None = None
    normalized_country: str | None = None
    normalized_state: str | None = None
    location_source: str | None = None
    role_eligibility: str | None = None
    role_eligibility_reason: str | None = None
    recommended_profile: str | None = None
    profile_scores: dict[str, float] = field(default_factory=dict)
    matched_title_patterns: list[str] = field(default_factory=list)
    normalized_title: str | None = None
    freshness_bucket: str | None = None
    freshness_tier: str | None = None
    freshness_source: str | None = None
    effective_freshness_at: datetime | None = None
    freshness_hours: float | None = None
    provider_posted_at: datetime | None = None
    source_received_at: datetime | None = None
    salary_tier: str | None = None
    owner_visible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_codes": self.reason_codes,
            "reasons": self.reasons,
            "location_eligibility": self.location_eligibility,
            "location_reason": self.location_reason,
            "normalized_country": self.normalized_country,
            "normalized_state": self.normalized_state,
            "location_source": self.location_source,
            "role_eligibility": self.role_eligibility,
            "role_eligibility_reason": self.role_eligibility_reason,
            "recommended_profile": self.recommended_profile,
            "profile_scores": self.profile_scores,
            "matched_title_patterns": self.matched_title_patterns,
            "normalized_title": self.normalized_title,
            "freshness_bucket": self.freshness_bucket,
            "freshness_tier": self.freshness_tier,
            "freshness_source": self.freshness_source,
            "effective_freshness_at": self.effective_freshness_at.isoformat()
            if self.effective_freshness_at
            else None,
            "freshness_hours": self.freshness_hours,
            "provider_posted_at": self.provider_posted_at.isoformat() if self.provider_posted_at else None,
            "source_received_at": self.source_received_at.isoformat() if self.source_received_at else None,
            "salary_tier": self.salary_tier,
            "owner_visible": self.owner_visible,
        }


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, (int, float)):
        # Remote OK epoch seconds
        try:
            ts = float(value)
            if ts > 1_000_000_000_000:  # ms
                ts /= 1000.0
            return datetime.utcfromtimestamp(ts)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return _parse_dt(int(raw))
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
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


def _extract_state(location: str) -> str | None:
    m = US_STATE_ABBREV.search(location)
    if m:
        return m.group(1).upper()
    name_match = re.search(US_STATE_NAMES, location, re.I)
    if name_match:
        return name_match.group(0).title()
    return None


def evaluate_location(payload: dict) -> tuple[str, str, str | None, str | None, str]:
    """Return location_eligibility, reason, country, state, location_source."""
    location_raw = (payload.get("location") or "").strip()
    location = location_raw.lower()
    workplace = (payload.get("workplace_type") or "").lower()
    text = _text_blob(payload)
    policy = job_discovery_policy().get("geography", {})
    local_terms = [t.lower() for t in policy.get("local_hybrid", [])]
    country_code = (payload.get("country_code") or payload.get("country") or "").strip().upper()
    location_source = payload.get("location_source") or "payload.location"

    # Ignore truncated one-character locations from bad parsers
    if len(location_raw) == 1:
        return AMBIGUOUS, "Location truncated/unusable", None, None, location_source

    if any(re.search(p, text) for p in RELOCATION_MARKERS):
        return RELOCATION_REQUIRED_LOC, "Posting requires relocation or onsite-only outside preference", None, None, location_source

    foreign_hits = [p for p in FOREIGN_MARKERS if re.search(p, text)]
    state = _extract_state(location_raw) if location_raw else None
    us_hit = (
        country_code in {"US", "USA"}
        or any(re.search(p, text) for p in US_MARKERS)
        or bool(re.search(US_STATE_NAMES, text, re.I))
        or bool(state)
        or any(city in location for city in US_CITY_HINTS)
    )
    local_hit = any(term in text for term in local_terms)

    if foreign_hits and not us_hit:
        return (
            INELIGIBLE_FOREIGN,
            f"Foreign-only geography markers: {', '.join(foreign_hits[:3])}",
            "FOREIGN",
            state,
            location_source,
        )

    if local_hit and ("hybrid" in text or "onsite" in text or "on-site" in text or "office" in text or "pennsylvania" in text or " pa" in f" {text}"):
        return ELIGIBLE_LOCAL, "Local/hybrid Central Pennsylvania geography", "US", state or "PA", location_source

    if us_hit:
        return ELIGIBLE_US, "Explicit US eligibility or US location", "US", state, location_source

    if "remote" in text or "remote" in workplace or "remote" in location:
        if re.search(r"\b(worldwide|global|anywhere)\b", text) and not us_hit:
            return AMBIGUOUS, "Worldwide/global remote without explicit US eligibility", None, state, location_source
        return AMBIGUOUS, "Remote with no country/eligibility information", None, state, location_source

    if location.strip() in {"", "n/a", "not specified", "unspecified"}:
        return AMBIGUOUS, "Location unspecified", None, None, location_source

    # City-like US string without country: OWNER_REVIEW, not foreign
    if location and not us_hit and not local_hit and not foreign_hits:
        return AMBIGUOUS, f"Geography ambiguous for location: {location_raw[:80]}", None, state, location_source

    if location and not us_hit and not local_hit:
        return INELIGIBLE_FOREIGN, f"Non-US location without US eligibility: {location_raw[:80]}", "FOREIGN", state, location_source

    return AMBIGUOUS, "Geography could not be confirmed as US-eligible", None, state, location_source


def freshness_tier_for_hours(hours: float | None) -> str | None:
    if hours is None:
        return None
    policy = job_discovery_policy().get("freshness", {})
    today_h = float(policy.get("today_hours", 24))
    fresh_h = float(policy.get("fresh_hours", 72))
    recent_h = float(policy.get("recent_hours", 168))
    if hours <= today_h:
        return TIER_TODAY
    if hours <= fresh_h:
        return TIER_FRESH
    if hours <= recent_h:
        return TIER_RECENT
    return TIER_HISTORICAL


def evaluate_freshness(
    payload: dict,
    *,
    now: datetime | None = None,
    allow_discovered_at: bool = False,
) -> tuple[str | None, str | None, datetime | None, float | None, datetime | None, datetime | None, list[str], list[str]]:
    """Return tier, source, effective_at, hours, provider_posted_at, source_received_at, codes, reasons."""
    now = now or datetime.utcnow()
    provider_posted_at = _parse_dt(
        payload.get("provider_posted_at") or payload.get("posted_at") or payload.get("publication_date")
    )
    source_received_at = _parse_dt(payload.get("source_received_at") or payload.get("received_at"))
    connector_fetched_at = _parse_dt(payload.get("connector_fetched_at") or payload.get("fetched_at"))
    discovered_at = _parse_dt(payload.get("discovered_at")) or now

    codes: list[str] = []
    reasons: list[str] = []
    effective: datetime | None = None
    source: str | None = None

    if provider_posted_at:
        effective = provider_posted_at
        source = "provider_posted_at"
    elif source_received_at:
        effective = source_received_at
        source = "source_received_at"
    elif connector_fetched_at:
        effective = connector_fetched_at
        source = "connector_fetched_at"
        codes.append(FRESHNESS_FALLBACK_USED)
        reasons.append("Using connector fetched_at as low-trust freshness fallback")
    elif allow_discovered_at or payload.get("source") in {"user_forwarded_links", "manual_opportunity"}:
        effective = discovered_at
        source = "discovered_at"
        codes.append(FRESHNESS_FALLBACK_USED)
        reasons.append("Using discovered_at as freshness fallback for manual/confirmed job")
    elif payload.get("discovered_at"):
        effective = discovered_at
        source = "discovered_at"
        codes.append(FRESHNESS_FALLBACK_USED)
        reasons.append("Using discovered_at as low-trust freshness fallback")
    else:
        return None, None, None, None, provider_posted_at, source_received_at, [TIMESTAMP_UNKNOWN], [
            "No reliable posted_at, received_at, or connector timestamp"
        ]

    hours = max(0.0, (now - effective).total_seconds() / 3600.0)
    tier = freshness_tier_for_hours(hours)
    return tier, source, effective, hours, provider_posted_at, source_received_at, codes, reasons


def _phrase_contiguous_in_tokens(pattern: str, haystack_tokens: list[str]) -> bool:
    """True when the normalized pattern appears as a contiguous token run.

    Contiguous-only (no loose subsequence) to avoid false positives across long
    descriptions — e.g. "manufacturing quality" must appear adjacent, not merely
    with both tokens somewhere in the text.
    """
    needle = title_tokens(pattern)
    if not needle or not haystack_tokens:
        return False
    n = len(needle)
    for i in range(len(haystack_tokens) - n + 1):
        if haystack_tokens[i : i + n] == needle:
            return True
    return False


def score_role_profiles(payload: dict) -> tuple[str | None, str | None, str | None, dict[str, float], list[str], str]:
    """Match role profiles against normalized TITLE only (not description)."""
    title = payload.get("title") or ""
    norm_title = normalize_title(title)
    text_for_require = normalize_title(
        " ".join(
            [
                title,
                payload.get("description_text") or "",
            ]
        )
    )
    profiles = job_discovery_policy().get("role_profiles", [])
    reject_patterns = list(job_discovery_policy().get("role_reject_patterns", []))
    domain_reject_patterns = list(job_discovery_policy().get("domain_reject_patterns", []))

    # Out-of-scope TITLE patterns (e.g. "air quality", "design quality engineering",
    # "supplier quality") must reject BEFORE any primary QE profile match — otherwise a
    # title that also resembles a target profile (…"Quality Engineer") is auto-accepted.
    for rp in reject_patterns:
        if rp and pattern_in_title(rp, title):
            return "reject", f"Title matches out-of-scope pattern: {rp}", None, {}, [], norm_title

    # Full-text (title + company + HTML-stripped description) domain exclusion runs
    # BEFORE any primary title acceptance so manufacturing / pharma / hardware quality
    # roles whose non-software nature only appears in the body cannot be auto-accepted.
    # HTML is stripped first so tags (e.g. "Supplier <b>Quality</b>") do not split
    # phrase matches into non-adjacent tokens.
    if domain_reject_patterns:
        blob_tokens = title_tokens(
            " ".join(
                [
                    title,
                    payload.get("company") or "",
                    html_to_text(payload.get("description_text") or ""),
                ]
            )
        )
        for dp in domain_reject_patterns:
            if _phrase_contiguous_in_tokens(dp, blob_tokens):
                return (
                    "reject",
                    f"Description matches out-of-scope domain: {dp}",
                    None,
                    {},
                    [],
                    norm_title,
                )

    scores: dict[str, float] = {}
    best_primary: tuple[float, str | None, list[str]] = (0.0, None, [])
    best_secondary: tuple[float, str | None, list[str]] = (0.0, None, [])

    for profile in profiles:
        pid = profile["id"]
        patterns = profile.get("title_patterns", [])
        hits = [p for p in patterns if pattern_in_title(p, title)]
        score = 0.0
        if hits:
            score = 50.0 + 20.0 * len(hits)
            score += max(len(normalize_title(p)) for p in hits) * 0.4
            require_any = [normalize_title(r) for r in profile.get("require_any", [])]
            if require_any:
                if not any(r and r in text_for_require for r in require_any):
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
            norm_title,
        )

    if best_secondary[1]:
        return (
            "secondary",
            f"Secondary-review profile: {best_secondary[1]}",
            best_secondary[1],
            scores,
            best_secondary[2],
            norm_title,
        )

    return "reject", "No target role profile matched", None, scores, [], norm_title


def salary_tier_for(payload: dict) -> tuple[str, list[str], list[str]]:
    policy = job_discovery_policy().get("salary", {})
    target = int(policy.get("target_max_usd", 200000))
    strong = int(policy.get("strong_max_usd", 170000))
    published = payload.get("salary_max") or payload.get("salary_min")
    codes: list[str] = []
    reasons: list[str] = []
    if published is None:
        return SALARY_UNKNOWN, codes, reasons
    value = int(published)
    if value >= target:
        return SALARY_TARGET, codes, reasons
    if value >= strong:
        return SALARY_STRONG, codes, reasons
    codes.append(COMPENSATION_REVIEW)
    reasons.append(f"Published compensation ${value} below strong band ${strong} — ranking REVIEW, not reject")
    return SALARY_REVIEW, codes, reasons


def is_saved_search_url(url: str) -> bool:
    if not url:
        return True
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    qs = parse_qs(parsed.query)
    if "linkedin.com" in host:
        if re.search(r"/jobs/view/\d+", path):
            return False
        if "/jobs/search" in path or "/jobs/collections" in path or "saved" in path:
            return True
        return True
    if "indeed.com" in host:
        if "jk" in qs or "/viewjob" in path:
            return False
        if "/jobs" in path or "q=" in parsed.query:
            return True
    return False


def _is_protected_state(payload: dict) -> bool:
    state = (payload.get("state") or payload.get("workflow_state") or "").upper()
    if state in PROTECTED_STATES:
        return True
    if payload.get("owner_confirmed") or payload.get("manual_confirmed"):
        return True
    if payload.get("source") in {"user_forwarded_links", "manual_opportunity"} and payload.get("owner_confirmed"):
        return True
    return False


def _default_visible_tiers() -> set[str]:
    tiers = job_discovery_policy().get("freshness", {}).get("default_visible_tiers") or [
        TIER_TODAY,
        TIER_FRESH,
        TIER_RECENT,
    ]
    return set(tiers)


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
    protected = _is_protected_state(payload)

    if any(re.search(p, text) for p in CLOSED_MARKERS):
        result.decision = DECISION_REJECT
        result.reason_codes.append(CLOSED_POSTING)
        result.reasons.append("Posting is closed or no longer accepting applications")
        result.owner_visible = False
        return result

    if is_saved_search_url(url):
        result.decision = DECISION_REJECT
        result.reason_codes.append(SAVED_SEARCH_URL_NOT_JOB_URL)
        result.reasons.append("URL is a saved-search or listing page, not a job posting")
        result.owner_visible = False
        return result

    bad_titles = {
        "linkedin job alert",
        "indeed job alert",
        "job alert",
        "linkedin role",
        "indeed role",
        "unparsed_linkedin_entry",
    }
    if title.lower() in bad_titles or not title or len(title) < 4:
        result.decision = DECISION_QUARANTINE
        result.reason_codes.append(MALFORMED_DIGEST)
        result.reasons.append("Title could not be extracted reliably from alert/digest")
        result.owner_visible = False
        return result

    bad_companies = {
        "unknown employer",
        "unknown company",
        "unknown",
        "",
        "penndot",
        "match your interests.",
        "match your interests",
    }
    if company.lower().strip() in bad_companies or "match your interests" in company.lower():
        result.reason_codes.append(COMPANY_UNKNOWN)
        result.reasons.append("Company/employer could not be extracted reliably")

    loc, loc_reason, country, state, loc_source = evaluate_location(payload)
    result.location_eligibility = loc
    result.location_reason = loc_reason
    result.normalized_country = country
    result.normalized_state = state
    result.location_source = loc_source
    if loc == INELIGIBLE_FOREIGN:
        result.decision = DECISION_REJECT
        result.reason_codes.append(FOREIGN_ONLY)
        result.reasons.append(loc_reason)
        result.owner_visible = False
        return result
    if loc == RELOCATION_REQUIRED_LOC:
        result.decision = DECISION_REJECT
        result.reason_codes.append(RELOCATION_REQUIRED)
        result.reasons.append(loc_reason)
        result.owner_visible = False
        return result
    if loc == AMBIGUOUS:
        result.reason_codes.append(REMOTE_ELIGIBILITY_AMBIGUOUS)
        result.reason_codes.append(OWNER_REVIEW)
        result.reasons.append(loc_reason)
        if result.decision == DECISION_ACCEPT:
            result.decision = DECISION_OWNER_REVIEW

    role_elig, role_reason, recommended, scores, matched, norm_title = score_role_profiles(payload)
    result.role_eligibility = role_elig
    result.role_eligibility_reason = role_reason
    result.recommended_profile = recommended
    result.profile_scores = scores
    result.matched_title_patterns = matched
    result.normalized_title = norm_title
    if role_elig == "reject":
        result.decision = DECISION_REJECT
        result.reason_codes.append(ROLE_OUT_OF_SCOPE)
        result.reasons.append(role_reason)
        result.owner_visible = False
        return result
    if role_elig == "secondary" and result.decision == DECISION_ACCEPT:
        result.decision = DECISION_SECONDARY
        result.reasons.append(role_reason)

    if not skip_freshness:
        tier, fsource, effective, hours, posted, received, codes, reasons = evaluate_freshness(
            payload, now=now, allow_discovered_at=allow_discovered_at
        )
        result.freshness_bucket = tier
        result.freshness_tier = tier
        result.freshness_source = fsource
        result.effective_freshness_at = effective
        result.freshness_hours = hours
        result.provider_posted_at = posted
        result.source_received_at = received
        result.reason_codes.extend(codes)
        result.reasons.extend(reasons)

        if TIMESTAMP_UNKNOWN in codes:
            # Strong target roles go to OWNER_REVIEW, not reject
            if role_elig == "primary" and result.decision in {DECISION_ACCEPT, DECISION_SECONDARY, DECISION_OWNER_REVIEW}:
                result.decision = DECISION_OWNER_REVIEW
                result.reason_codes.append(OWNER_REVIEW)
                result.reasons.append("Strong target role with unknown timestamp — owner review")
            elif result.decision == DECISION_ACCEPT:
                result.decision = DECISION_OWNER_REVIEW
        elif tier == TIER_HISTORICAL and not protected:
            result.decision = DECISION_HISTORICAL
            result.reason_codes.append(STALE_HISTORICAL)
            result.reasons.append("Older than 7 days — historical, hidden from default Fresh Jobs")
        elif protected and tier == TIER_HISTORICAL:
            result.reasons.append("Protected workflow state — freshness age-out skipped")

    salary_tier, s_codes, s_reasons = salary_tier_for(payload)
    result.salary_tier = salary_tier
    result.reason_codes.extend(s_codes)
    result.reasons.extend(s_reasons)
    # Salary never hard-rejects

    if COMPANY_UNKNOWN in result.reason_codes and result.decision == DECISION_ACCEPT:
        result.decision = DECISION_OWNER_REVIEW

    visible_tiers = _default_visible_tiers()
    if protected:
        result.owner_visible = result.decision not in {DECISION_REJECT, DECISION_DUPLICATE}
    elif result.decision == DECISION_ACCEPT and result.freshness_tier in visible_tiers:
        result.owner_visible = True
    elif result.decision in {DECISION_OWNER_REVIEW, DECISION_SECONDARY, DECISION_QUARANTINE}:
        result.owner_visible = False  # review queues, not default Fresh Jobs
    else:
        result.owner_visible = False

    return result
