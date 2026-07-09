"""Fresh Jobs discovery policy loader and helpers."""

from __future__ import annotations

from functools import lru_cache

from app.services.config_loader import load_yaml


@lru_cache(maxsize=1)
def job_discovery_policy() -> dict:
    return load_yaml("config/job-discovery-policy.yml")


def clear_discovery_policy_cache() -> None:
    job_discovery_policy.cache_clear()


def freshness_max_age_hours() -> int:
    """Default Fresh Jobs visibility window (TODAY+FRESH+RECENT = 7 days)."""
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
