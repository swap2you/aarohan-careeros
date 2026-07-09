"""Policy-driven Fresh Jobs discovery campaign (replaces hardcoded GitLab public feed)."""

from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.services.connector_runner import run_connector
from app.services.discovery_policy import enabled_discovery_providers, job_discovery_policy


def _skipped_sources() -> list[dict]:
    """Sources enabled in policy but not runnable (missing keys / empty boards)."""
    from app.integrations.job_providers import get_provider

    sources = job_discovery_policy().get("sources", {})
    skipped: list[dict] = []
    for key, cfg in sources.items():
        if not isinstance(cfg, dict) or not cfg.get("enabled"):
            continue
        provider_id = cfg.get("provider_id")
        if not provider_id:
            # Email alert sources are not public-feed connectors
            skipped.append(
                {
                    "source_key": key,
                    "provider_id": None,
                    "reason": "not_a_public_feed_connector",
                }
            )
            continue
        if key in {"greenhouse", "lever", "ashby"}:
            boards = cfg.get("approved_boards") or []
            if not boards:
                skipped.append(
                    {
                        "source_key": key,
                        "provider_id": provider_id,
                        "reason": "no_approved_boards",
                    }
                )
            continue
        try:
            provider = get_provider(provider_id)
            if not provider.is_configured():
                skipped.append(
                    {
                        "source_key": key,
                        "provider_id": provider_id,
                        "reason": "not_configured",
                    }
                )
        except Exception:
            skipped.append(
                {
                    "source_key": key,
                    "provider_id": provider_id,
                    "reason": "provider_unavailable",
                }
            )
    return skipped


def discover_fresh_jobs(db: Session, *, actor: str, use_fixture: bool = False) -> dict:
    """Run configured discovery providers with eligibility gates.

    Greenhouse/Lever/Ashby boards are only included when explicitly listed in
    config/job-discovery-policy.yml approved_boards (default empty).
    """
    campaigns = enabled_discovery_providers()
    sources: list[dict] = []
    source_errors: list[dict] = []
    totals = Counter()
    skipped = _skipped_sources()
    attempted = [{"source_key": c.get("source_key"), "provider_id": c["provider_id"], "board": c.get("board")} for c in campaigns]

    if not campaigns:
        message = (
            "No discovery campaigns configured. Enable Adzuna/Jooble/USAJOBS/Remotive/"
            "Remote OK/RSS keys, or add approved Greenhouse/Lever/Ashby boards."
        )
        return {
            "action": "discover_fresh_jobs",
            "fetched": 0,
            "accepted": 0,
            "owner_review": 0,
            "secondary_review": 0,
            "quarantined": 0,
            "rejected": 0,
            "duplicates": 0,
            "sources": [],
            "sources_attempted": attempted,
            "sources_skipped": skipped,
            "source_errors": [],
            "message": (
                f"{message} Attempted={len(attempted)} skipped={len(skipped)} "
                f"fetched=0 accepted=0 owner_review=0 quarantined=0 rejected=0 duplicates=0."
            ),
        }

    for campaign in campaigns:
        provider_id = campaign["provider_id"]
        params: dict = {}
        board = campaign.get("board")
        if board:
            if isinstance(board, dict):
                params = {**board}
            else:
                if provider_id == "greenhouse":
                    params = {"board_token": str(board)}
                elif provider_id == "lever":
                    params = {"company_slug": str(board)}
                elif provider_id == "ashby":
                    params = {"job_board_name": str(board)}
                else:
                    params = {"board": str(board)}
        try:
            result = run_connector(
                db,
                provider_id,
                actor=actor,
                use_fixture=use_fixture,
                params=params or None,
            )
        except Exception as exc:
            err = str(exc)[:240]
            result = {
                "provider_id": provider_id,
                "fetched": 0,
                "accepted": 0,
                "secondary_review": 0,
                "owner_review": 0,
                "quarantined": 0,
                "rejected": 0,
                "duplicates": 0,
                "message": err,
                "health_state": "ERROR",
            }
            source_errors.append({"source_key": campaign.get("source_key"), "provider_id": provider_id, "error": err})
        if result.get("health_state") == "ERROR" and result.get("message"):
            source_errors.append(
                {
                    "source_key": campaign.get("source_key"),
                    "provider_id": provider_id,
                    "error": result.get("message"),
                }
            )
        owner_review = int(result.get("owner_review") or result.get("secondary_review") or 0)
        sources.append(
            {
                "source_key": campaign.get("source_key"),
                "provider_id": provider_id,
                "board": board,
                "fetched": result.get("fetched", 0),
                "accepted": result.get("accepted", 0),
                "owner_review": owner_review,
                "secondary_review": result.get("secondary_review", 0),
                "quarantined": result.get("quarantined", 0),
                "rejected": result.get("rejected", 0),
                "duplicates": result.get("duplicates", 0),
                "health_state": result.get("health_state"),
                "message": result.get("message"),
                "run_id": result.get("run_id"),
                "reason_distribution": result.get("reason_distribution") or {},
            }
        )
        for key in ("fetched", "accepted", "secondary_review", "quarantined", "rejected", "duplicates"):
            totals[key] += int(result.get(key) or 0)
        totals["owner_review"] += owner_review

    message = (
        f"sources_attempted={len(attempted)} sources_skipped={len(skipped)} "
        f"fetched={totals['fetched']} accepted={totals['accepted']} "
        f"owner_review={totals['owner_review']} quarantined={totals['quarantined']} "
        f"rejected={totals['rejected']} duplicates={totals['duplicates']} "
        f"source_errors={len(source_errors)}"
    )
    return {
        "action": "discover_fresh_jobs",
        "fetched": totals["fetched"],
        "accepted": totals["accepted"],
        "owner_review": totals["owner_review"],
        "secondary_review": totals["secondary_review"],
        "quarantined": totals["quarantined"],
        "rejected": totals["rejected"],
        "duplicates": totals["duplicates"],
        "sources": sources,
        "sources_attempted": attempted,
        "sources_skipped": skipped,
        "source_errors": source_errors,
        "message": message,
    }
