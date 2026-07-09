"""Policy-driven Fresh Jobs discovery campaign (replaces hardcoded GitLab public feed)."""

from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.services.connector_runner import run_connector
from app.services.discovery_policy import enabled_discovery_providers


def discover_fresh_jobs(db: Session, *, actor: str, use_fixture: bool = False) -> dict:
    """Run configured discovery providers with eligibility gates.

    Greenhouse/Lever/Ashby boards are only included when explicitly listed in
    config/job-discovery-policy.yml approved_boards (default empty).
    """
    campaigns = enabled_discovery_providers()
    sources: list[dict] = []
    totals = Counter()

    if not campaigns:
        return {
            "action": "discover_fresh_jobs",
            "fetched": 0,
            "accepted": 0,
            "secondary_review": 0,
            "quarantined": 0,
            "rejected": 0,
            "duplicates": 0,
            "sources": [],
            "message": (
                "No discovery campaigns configured. Enable Adzuna/Jooble/USAJOBS/Remotive/"
                "Remote OK/RSS keys, or add approved Greenhouse/Lever/Ashby boards."
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
                # Greenhouse uses board_token; Lever uses company_slug
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
            result = {
                "provider_id": provider_id,
                "fetched": 0,
                "accepted": 0,
                "secondary_review": 0,
                "quarantined": 0,
                "rejected": 0,
                "duplicates": 0,
                "message": str(exc)[:240],
                "health_state": "ERROR",
            }
        sources.append(
            {
                "source_key": campaign.get("source_key"),
                "provider_id": provider_id,
                "board": board,
                "fetched": result.get("fetched", 0),
                "accepted": result.get("accepted", 0),
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

    return {
        "action": "discover_fresh_jobs",
        "fetched": totals["fetched"],
        "accepted": totals["accepted"],
        "secondary_review": totals["secondary_review"],
        "quarantined": totals["quarantined"],
        "rejected": totals["rejected"],
        "duplicates": totals["duplicates"],
        "sources": sources,
    }
