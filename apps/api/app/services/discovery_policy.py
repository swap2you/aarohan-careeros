"""Fresh Jobs discovery policy loader and effective-policy resolution.

The **effective** discovery policy = immutable application defaults
(``config/job-discovery-policy.yml``) deep-merged with the compiled ``overrides`` of the
single active owner policy version (``discovery_policy_versions`` table).

To keep the hot eligibility path free of database access (and safe under the shared
in-memory test session), the active override is held in a module-level variable that is
refreshed explicitly:

- server startup calls :func:`refresh_active_override` once,
- the activate/restore endpoints call :func:`set_active_override` / :func:`refresh_active_override`.

With no active override (the default and unit-test state) the effective policy equals the
file defaults, so all existing behavior and tests are unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache

from app.services.config_loader import load_yaml

# In-memory compiled override of the active policy version (None => file defaults only).
_ACTIVE_OVERRIDE: dict | None = None


@lru_cache(maxsize=1)
def _load_defaults() -> dict:
    return load_yaml("config/job-discovery-policy.yml")


def discovery_policy_defaults() -> dict:
    """Immutable application defaults (deep copy so callers cannot mutate the cache)."""
    return copy.deepcopy(_load_defaults())


def defaults_fingerprint() -> str:
    return hashlib.sha256(
        json.dumps(_load_defaults(), sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into a deep copy of ``base``.

    Nested dicts merge; scalars and lists are replaced by the override value.
    """
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


@lru_cache(maxsize=1)
def _effective_cached(_override_signature: str) -> dict:
    override = json.loads(_override_signature) if _override_signature else {}
    return _deep_merge(_load_defaults(), override)


def job_discovery_policy() -> dict:
    """Return the effective discovery policy (defaults + active owner override).

    Kept under this historical name so every existing consumer automatically honors owner
    overrides. Returns file defaults when no override is active.
    """
    signature = json.dumps(_ACTIVE_OVERRIDE, sort_keys=True) if _ACTIVE_OVERRIDE else ""
    return _effective_cached(signature)


def effective_discovery_policy() -> dict:
    """Explicit alias for the effective policy."""
    return job_discovery_policy()


def set_active_override(override: dict | None) -> None:
    """Set the in-memory compiled active override and invalidate the effective cache."""
    global _ACTIVE_OVERRIDE
    _ACTIVE_OVERRIDE = copy.deepcopy(override) if override else None
    _effective_cached.cache_clear()


def refresh_active_override(db=None) -> dict:
    """Load the active policy version from the database and compile its override.

    Best-effort: any error (missing table, no session) falls back to file defaults so the
    hot path and unit tests never break.
    """
    from app.services.discovery_policy_service import (
        compile_overrides,
        get_active_version,
    )

    close_after = False
    try:
        if db is None:
            from app.database import SessionLocal

            db = SessionLocal()
            close_after = True
        version = get_active_version(db)
        override = compile_overrides(version.overrides) if version else None
        set_active_override(override)
        return override or {}
    except Exception:
        set_active_override(None)
        return {}
    finally:
        if close_after and db is not None:
            try:
                db.close()
            except Exception:
                pass


def clear_discovery_policy_cache() -> None:
    _load_defaults.cache_clear()
    _effective_cached.cache_clear()


def freshness_max_age_hours() -> int:
    """Default Fresh Jobs visibility window (TODAY+FRESH+RECENT = 7 days by default)."""
    freshness = job_discovery_policy().get("freshness", {})
    if "recent_hours" in freshness:
        return int(freshness["recent_hours"])
    return int(freshness.get("max_age_hours", 168))


def salary_strong_usd() -> int:
    return int(job_discovery_policy().get("salary", {}).get("strong_max_usd", 170000))


def salary_minimum_usd() -> int:
    # Legacy alias — compensation is ranking-only; strong band is the preference floor.
    return salary_strong_usd()


def owner_visible_fit_score() -> float:
    return float(job_discovery_policy().get("minimums", {}).get("owner_visible_fit_score", 55))


def enabled_discovery_providers() -> list[dict]:
    """Return configured discovery campaign providers (not company boards)."""
    sources = job_discovery_policy().get("sources", {})
    campaigns: list[dict] = []
    for key, cfg in sources.items():
        if not isinstance(cfg, dict) or not cfg.get("enabled"):
            continue
        provider_id = cfg.get("provider_id")
        if not provider_id:
            continue
        # Company ATS boards require explicit approved_boards entries.
        if key in {"greenhouse", "lever", "ashby"}:
            boards = cfg.get("approved_boards") or []
            if not boards:
                continue
            for board in boards:
                campaigns.append(
                    {
                        "source_key": key,
                        "provider_id": provider_id,
                        "board": board,
                    }
                )
            continue
        campaigns.append({"source_key": key, "provider_id": provider_id, "board": None})
    return campaigns
