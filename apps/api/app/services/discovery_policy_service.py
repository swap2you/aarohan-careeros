"""Versioned owner discovery-policy service.

Owner-facing overrides are stored as **validated data** (never executable expressions) in
``discovery_policy_versions.overrides`` using a small, whitelisted schema. They are compiled
into a policy-shaped override that is deep-merged onto the immutable file defaults to produce
the effective discovery policy.

Safety invariants (enforced regardless of preset / owner input):
- ``geography.foreign_only`` stays ``reject`` — foreign-only roles are never accepted.
- ``geography.relocation_required`` stays ``reject``.
- The default ``role_reject_patterns`` and ``domain_reject_patterns`` are always preserved
  (owner input can only *add* exclusions, never remove them).
- fixture/test provenance rows remain owner-excluded (handled at the query layer).
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DiscoveryPolicyVersion
from app.services.discovery_policy import (
    defaults_fingerprint,
    discovery_policy_defaults,
    refresh_active_override,
    set_active_override,
)

ALLOWED_FRESHNESS_DAYS = {3, 7, 14, 30}
ALLOWED_TIERS = {"TODAY", "FRESH", "RECENT", "HISTORICAL"}
ALLOWED_GEO_ACTIONS = {"accept", "owner_review", "reject"}
ALLOWED_SENSITIVITY = {"strict", "balanced", "broad"}
GMAIL_SOURCE_KEYS = {
    "linkedin_alert_emails",
    "indeed_alert_emails",
    "dice_alert_emails",
    "usajobs_alert_emails",
    "glassdoor_alert_emails",
}
PUBLIC_PROVIDER_KEYS = {
    "adzuna",
    "jooble",
    "usajobs",
    "remotive",
    "remote_ok",
    "rss",
    "greenhouse",
    "lever",
    "ashby",
}
ALLOWED_OVERRIDE_KEYS = {
    "freshness_days",
    "visible_tiers",
    "primary_families",
    "include_secondary",
    "title_include",
    "title_exclude",
    "domain_exclude",
    "remote_us",
    "remote_unspecified",
    "local_hybrid",
    "salary_target_usd",
    "salary_strong_usd",
    "providers",
    "gmail_sources",
    "owner_review_sensitivity",
}
_MAX_LIST = 200
_MAX_PHRASE = 200

# Serialize the preview global-swap so concurrent previews cannot interleave overrides.
_PREVIEW_LOCK = threading.RLock()


class PolicyValidationError(ValueError):
    """Raised when an owner override fails schema validation."""


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------
def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PolicyValidationError(message)


def _clean_phrases(value, field: str) -> list[str]:
    _require(isinstance(value, list), f"{field} must be a list")
    _require(len(value) <= _MAX_LIST, f"{field} too long")
    out: list[str] = []
    for item in value:
        _require(isinstance(item, str), f"{field} entries must be strings")
        item = item.strip()
        _require(0 < len(item) <= _MAX_PHRASE, f"{field} entries must be 1..{_MAX_PHRASE} chars")
        out.append(item)
    return out


def validate_overrides(raw: dict | None) -> dict:
    """Validate and normalize an owner override, returning a clean copy."""
    raw = raw or {}
    _require(isinstance(raw, dict), "overrides must be an object")
    unknown = set(raw.keys()) - ALLOWED_OVERRIDE_KEYS
    _require(not unknown, f"unknown override keys: {sorted(unknown)}")

    out: dict = {}
    if "freshness_days" in raw:
        _require(raw["freshness_days"] in ALLOWED_FRESHNESS_DAYS, "freshness_days must be 3/7/14/30")
        out["freshness_days"] = int(raw["freshness_days"])
    if "visible_tiers" in raw:
        tiers = raw["visible_tiers"]
        _require(isinstance(tiers, list) and tiers, "visible_tiers must be a non-empty list")
        _require(set(tiers) <= ALLOWED_TIERS, f"visible_tiers must be subset of {sorted(ALLOWED_TIERS)}")
        out["visible_tiers"] = [t for t in ["TODAY", "FRESH", "RECENT", "HISTORICAL"] if t in tiers]
    if "primary_families" in raw:
        pf = raw["primary_families"]
        _require(isinstance(pf, dict), "primary_families must be an object")
        clean = {}
        for k, v in pf.items():
            _require(isinstance(k, str) and isinstance(v, bool), "primary_families map string->bool")
            clean[k] = v
        out["primary_families"] = clean
    if "include_secondary" in raw:
        _require(isinstance(raw["include_secondary"], bool), "include_secondary must be bool")
        out["include_secondary"] = raw["include_secondary"]
    if "title_include" in raw:
        out["title_include"] = _clean_phrases(raw["title_include"], "title_include")
    if "title_exclude" in raw:
        out["title_exclude"] = _clean_phrases(raw["title_exclude"], "title_exclude")
    if "domain_exclude" in raw:
        out["domain_exclude"] = _clean_phrases(raw["domain_exclude"], "domain_exclude")
    for geo_key in ("remote_us", "remote_unspecified"):
        if geo_key in raw:
            _require(raw[geo_key] in ALLOWED_GEO_ACTIONS, f"{geo_key} must be accept/owner_review/reject")
            out[geo_key] = raw[geo_key]
    if "local_hybrid" in raw:
        out["local_hybrid"] = _clean_phrases(raw["local_hybrid"], "local_hybrid")
    for sal_key in ("salary_target_usd", "salary_strong_usd"):
        if sal_key in raw:
            _require(
                isinstance(raw[sal_key], int) and 0 < raw[sal_key] <= 2_000_000,
                f"{sal_key} must be a positive integer",
            )
            out[sal_key] = int(raw[sal_key])
    if "providers" in raw:
        prov = raw["providers"]
        _require(isinstance(prov, dict), "providers must be an object")
        clean = {}
        for k, v in prov.items():
            _require(k in PUBLIC_PROVIDER_KEYS, f"unknown provider: {k}")
            _require(isinstance(v, bool), "providers map string->bool")
            clean[k] = v
        out["providers"] = clean
    if "gmail_sources" in raw:
        gm = raw["gmail_sources"]
        _require(isinstance(gm, dict), "gmail_sources must be an object")
        clean = {}
        for k, v in gm.items():
            _require(k in GMAIL_SOURCE_KEYS, f"unknown gmail source: {k}")
            _require(isinstance(v, bool), "gmail_sources map string->bool")
            clean[k] = v
        out["gmail_sources"] = clean
    if "owner_review_sensitivity" in raw:
        _require(
            raw["owner_review_sensitivity"] in ALLOWED_SENSITIVITY,
            "owner_review_sensitivity must be strict/balanced/broad",
        )
        out["owner_review_sensitivity"] = raw["owner_review_sensitivity"]
    return out


# --------------------------------------------------------------------------------------
# Compile owner override -> policy-shaped override (for deep-merge onto defaults)
# --------------------------------------------------------------------------------------
def compile_overrides(raw: dict | None) -> dict:
    """Translate a validated owner override into a policy-shaped override.

    Additive fields (reject patterns, domain exclusions) are merged with the defaults here so
    the subsequent deep-merge (which replaces lists) preserves the built-in safety rules.
    """
    raw = validate_overrides(raw)
    defaults = discovery_policy_defaults()
    out: dict = {}

    # Freshness / tiers
    freshness: dict = {}
    if "freshness_days" in raw:
        freshness["recent_hours"] = raw["freshness_days"] * 24
    if "visible_tiers" in raw:
        freshness["default_visible_tiers"] = raw["visible_tiers"]
    if freshness:
        out["freshness"] = freshness

    # Geography (foreign_only / relocation_required are never overridable)
    geography: dict = {}
    for key in ("remote_us", "remote_unspecified"):
        if key in raw:
            geography[key] = raw[key]
    if "local_hybrid" in raw:
        geography["local_hybrid"] = raw["local_hybrid"]
    if geography:
        out["geography"] = geography

    # Role profiles: disable primary families, drop/keep secondary, add custom include
    primary_families = raw.get("primary_families", {})
    include_secondary = raw.get("include_secondary", True)
    profiles = []
    for profile in defaults.get("role_profiles", []):
        pid = profile.get("id")
        eligibility = profile.get("eligibility")
        if eligibility == "primary" and primary_families.get(pid) is False:
            continue
        if eligibility == "secondary" and not include_secondary:
            continue
        profiles.append(copy.deepcopy(profile))
    if raw.get("title_include"):
        profiles.append(
            {
                "id": "owner_custom_include",
                "label": "Owner custom include",
                "eligibility": "primary",
                "title_patterns": [p.lower() for p in raw["title_include"]],
            }
        )
    if primary_families or "include_secondary" in raw or raw.get("title_include"):
        out["role_profiles"] = profiles

    # Additive exclusions — always preserve defaults, only add
    if raw.get("title_exclude"):
        base = list(defaults.get("role_reject_patterns", []))
        for phrase in raw["title_exclude"]:
            low = phrase.lower()
            if low not in base:
                base.append(low)
        out["role_reject_patterns"] = base
    if raw.get("domain_exclude"):
        base = list(defaults.get("domain_reject_patterns", []))
        for phrase in raw["domain_exclude"]:
            low = phrase.lower()
            if low not in base:
                base.append(low)
        out["domain_reject_patterns"] = base

    # Salary bands (ranking/review only — never a hard reject)
    salary: dict = {}
    if "salary_target_usd" in raw:
        salary["target_max_usd"] = raw["salary_target_usd"]
    if "salary_strong_usd" in raw:
        salary["strong_max_usd"] = raw["salary_strong_usd"]
    if salary:
        out["salary"] = salary

    # Sources: public providers + gmail alert sources
    sources: dict = {}
    for key, enabled in raw.get("providers", {}).items():
        sources.setdefault(key, {})["enabled"] = enabled
    for key, enabled in raw.get("gmail_sources", {}).items():
        sources.setdefault(key, {})["enabled"] = enabled
    if sources:
        out["sources"] = sources

    if "owner_review_sensitivity" in raw:
        out["owner_review_sensitivity"] = raw["owner_review_sensitivity"]

    return out


# --------------------------------------------------------------------------------------
# Presets
# --------------------------------------------------------------------------------------
def preset_overrides(name: str) -> dict:
    """Return the RAW owner override for a named preset.

    Broad widens freshness/secondary/owner-review sensitivity but is **not** unfiltered:
    foreign-only, clearly unrelated (reject patterns), and fixture/test rows stay excluded.
    """
    name = (name or "").lower()
    if name == "strict":
        return {
            "freshness_days": 3,
            "visible_tiers": ["TODAY", "FRESH"],
            "include_secondary": False,
            "remote_unspecified": "reject",
            "owner_review_sensitivity": "strict",
        }
    if name == "broad":
        return {
            "freshness_days": 14,
            "visible_tiers": ["TODAY", "FRESH", "RECENT", "HISTORICAL"],
            "include_secondary": True,
            "remote_unspecified": "owner_review",
            "owner_review_sensitivity": "broad",
        }
    # balanced (default) == file defaults, no override
    return {}


def preset_names() -> list[str]:
    return ["strict", "balanced", "broad"]


# --------------------------------------------------------------------------------------
# Versioning
# --------------------------------------------------------------------------------------
def get_active_version(db: Session) -> DiscoveryPolicyVersion | None:
    return db.execute(
        select(DiscoveryPolicyVersion).where(DiscoveryPolicyVersion.status == "active")
    ).scalars().first()


def list_versions(db: Session) -> list[DiscoveryPolicyVersion]:
    return list(
        db.execute(
            select(DiscoveryPolicyVersion).order_by(DiscoveryPolicyVersion.version.desc())
        ).scalars()
    )


def _next_version_number(db: Session) -> int:
    rows = db.execute(select(DiscoveryPolicyVersion.version)).scalars().all()
    return (max(rows) + 1) if rows else 1


def create_draft(
    db: Session,
    raw_override: dict | None,
    *,
    preset: str | None = None,
    label: str | None = None,
    notes: str | None = None,
    created_by: str | None = None,
) -> DiscoveryPolicyVersion:
    """Validate and persist a new draft policy version (does not activate it)."""
    clean = validate_overrides(raw_override)
    version = DiscoveryPolicyVersion(
        version=_next_version_number(db),
        status="draft",
        preset=preset,
        label=label,
        notes=notes,
        overrides=clean,
        defaults_fingerprint=defaults_fingerprint(),
        created_by=created_by,
        created_at=datetime.utcnow(),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def activate_version(
    db: Session, version_id: int, *, activated_by: str | None = None
) -> DiscoveryPolicyVersion:
    """Archive the current active version and activate ``version_id`` (single active row)."""
    target = db.get(DiscoveryPolicyVersion, version_id)
    if target is None:
        raise PolicyValidationError(f"policy version {version_id} not found")
    # Re-validate stored overrides before activation (defense in depth).
    validate_overrides(target.overrides)
    for current in db.execute(
        select(DiscoveryPolicyVersion).where(DiscoveryPolicyVersion.status == "active")
    ).scalars():
        current.status = "archived"
    target.status = "active"
    target.activated_by = activated_by
    target.activated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)
    # Update the hot-path effective policy.
    set_active_override(compile_overrides(target.overrides))
    return target


def restore_defaults(db: Session, *, actor: str | None = None) -> DiscoveryPolicyVersion:
    """Create and activate an empty (defaults-only) policy version."""
    version = create_draft(
        db, {}, preset="balanced", label="Restore defaults", created_by=actor
    )
    return activate_version(db, version.id, activated_by=actor)


# --------------------------------------------------------------------------------------
# Effective + preview
# --------------------------------------------------------------------------------------
def effective_from_overrides(raw_override: dict | None) -> dict:
    """Compute the effective policy dict for a candidate override (no persistence)."""
    from app.services.discovery_policy import _deep_merge

    return _deep_merge(discovery_policy_defaults(), compile_overrides(raw_override))


def preview_policy(
    db: Session,
    raw_override: dict | None,
    *,
    sample_limit: int = 8,
    now: datetime | None = None,
) -> dict:
    """Preview a candidate override against existing recent owner records.

    Runs the real deterministic eligibility engine under the candidate policy (temporarily
    swapped in-process, then restored) and reports would-accept/review/quarantine/reject
    counts, per-group examples, and a before/after delta versus the current effective policy.
    """
    from app.models import Job
    from app.services.discovery_policy import job_discovery_policy
    from app.services.job_eligibility import (
        DECISION_ACCEPT,
        DECISION_DUPLICATE,
        DECISION_HISTORICAL,
        DECISION_OWNER_REVIEW,
        DECISION_QUARANTINE,
        DECISION_REJECT,
        DECISION_SECONDARY,
        evaluate_owner_decision,
    )
    from app.services.provenance import OWNER_EXCLUDED

    now = now or datetime.utcnow()
    candidate_override = compile_overrides(raw_override)

    def _bucket(decision: str) -> str:
        if decision == DECISION_ACCEPT:
            return "would_accept"
        if decision == DECISION_OWNER_REVIEW:
            return "would_owner_review"
        if decision in {DECISION_SECONDARY, DECISION_QUARANTINE}:
            return "would_quarantine"
        return "would_reject"  # REJECT, DUPLICATE, HISTORICAL

    def _payload(job: Job) -> dict:
        return {
            "source": job.source,
            "external_id": job.external_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description_text": job.description_text,
            "description_html": job.description_html,
            "url": job.url,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "provider_posted_at": job.provider_posted_at,
            "source_received_at": job.source_received_at,
            "discovered_at": job.discovered_at,
            "workplace_type": job.workplace_type,
            "persisted_ingest_decision": job.ingest_decision,
            "persisted_reason_codes": job.ingest_reason_codes,
        }

    jobs = (
        db.query(Job)
        .filter(~Job.data_provenance.in_(OWNER_EXCLUDED))
        .order_by(Job.effective_freshness_at.desc().nullslast())
        .all()
    )

    def _evaluate_all() -> dict[int, str]:
        return {job.id: evaluate_owner_decision(_payload(job), now=now).decision for job in jobs}

    from app.services.discovery_policy import _ACTIVE_OVERRIDE  # snapshot current

    with _PREVIEW_LOCK:
        previous_override = copy.deepcopy(_ACTIVE_OVERRIDE)
        try:
            # Current effective decisions (as configured now)
            before = _evaluate_all()
            # Candidate effective decisions
            set_active_override(candidate_override)
            # sanity touch to ensure cache uses candidate
            job_discovery_policy()
            after = _evaluate_all()
        finally:
            set_active_override(previous_override)

    counts = {"would_accept": 0, "would_owner_review": 0, "would_quarantine": 0, "would_reject": 0}
    examples: dict[str, list] = {k: [] for k in counts}
    changed = []
    by_id = {job.id: job for job in jobs}
    for job_id, decision in after.items():
        bucket = _bucket(decision)
        counts[bucket] += 1
        if len(examples[bucket]) < sample_limit:
            job = by_id[job_id]
            examples[bucket].append(
                {"id": job.id, "title": job.title, "company": job.company, "decision": decision}
            )
        if before.get(job_id) != decision:
            job = by_id[job_id]
            changed.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "before": before.get(job_id),
                    "after": decision,
                }
            )

    before_counts = {"would_accept": 0, "would_owner_review": 0, "would_quarantine": 0, "would_reject": 0}
    for decision in before.values():
        before_counts[_bucket(decision)] += 1

    return {
        "evaluated_at": now.isoformat(),
        "sample_size": len(jobs),
        "counts": counts,
        "before_counts": before_counts,
        "delta": {k: counts[k] - before_counts[k] for k in counts},
        "examples": examples,
        "changed": changed[: sample_limit * 4],
        "changed_count": len(changed),
    }
