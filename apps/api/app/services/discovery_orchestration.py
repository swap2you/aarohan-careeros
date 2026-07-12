"""Unified discovery orchestration (Workflow 01.5, Section 4).

One owner-facing operation, "Run Job Discovery", executes a controlled sequence:
  1. Gmail job-alert discovery and replay
  2. configured public / API providers
  3. configured approved ATS boards
  4..7. normalization / dedup / eligibility / persistence (inside each connector + Gmail sync)
  8. source-result summary

The legacy "Ingest Public Feed" behavior remains internally supported via
``discover_fresh_jobs`` (public + ATS only); this orchestrator adds the Gmail stage so the
owner UI never implies public discovery includes Gmail when it does not.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.discovery_policy import job_discovery_policy
from app.services.fresh_jobs_discovery import discover_fresh_jobs

_ATS_KEYS = {"greenhouse", "lever", "ashby"}
_ZERO = {
    "fetched": 0,
    "accepted": 0,
    "owner_review": 0,
    "quarantined": 0,
    "rejected": 0,
    "duplicates": 0,
    "errors": 0,
}


def run_gmail_discovery(db: Session, *, actor: str, use_fixture: bool = False) -> dict:
    """Gmail job-alert discovery + replay. Best-effort; captures errors, never raises."""
    result: dict = {
        "stage": "gmail",
        "attempted": True,
        "skipped": False,
        "skip_reason": None,
        **_ZERO,
        "messages_processed": 0,
        "jobs_produced": 0,
        "error": None,
    }
    policy_sources = job_discovery_policy().get("sources", {})
    gmail_enabled = any(
        isinstance(policy_sources.get(k), dict) and policy_sources[k].get("enabled")
        for k in ("linkedin_alert_emails", "indeed_alert_emails")
    )
    if not gmail_enabled and not use_fixture:
        result.update({"attempted": False, "skipped": True, "skip_reason": "no_gmail_alert_sources_enabled"})
        return result
    try:
        from app.services.gmail_lifecycle import sync_messages

        if use_fixture:
            from app.integrations.google import FixtureGmailClient

            messages = FixtureGmailClient().fetch_recent_messages(max_results=50)
            source = "gmail_fixture"
        else:
            from app.services.google_api import fetch_aarohan_labeled_messages

            messages = fetch_aarohan_labeled_messages(db, max_results=50)
            source = "gmail"
        synced = sync_messages(db, messages, source=source, actor=actor)
        # sync_messages returns a summary dict; surface common counters if present.
        result["messages_processed"] = int(synced.get("processed", synced.get("total", 0)) or 0)
        result["jobs_produced"] = int(synced.get("jobs", synced.get("accepted", 0)) or 0)
        result["accepted"] = result["jobs_produced"]
        result["gmail_summary"] = synced
    except Exception as exc:  # noqa: BLE001 — orchestration must not crash on a single stage
        result["error"] = str(exc)[:240]
        result["errors"] = 1
        result["skip_reason"] = "gmail_unavailable"
    return result


def run_all_discovery(db: Session, *, actor: str, use_fixture: bool = False) -> dict:
    """Run Gmail + public + ATS discovery in sequence and return a unified summary."""
    started = datetime.utcnow()
    gmail = run_gmail_discovery(db, actor=actor, use_fixture=use_fixture)
    public_result = discover_fresh_jobs(db, actor=actor, use_fixture=use_fixture)

    public_sources = []
    ats_sources = []
    for src in public_result.get("sources", []):
        (ats_sources if src.get("source_key") in _ATS_KEYS else public_sources).append(src)

    totals = Counter()
    for stage_counts in (gmail,):
        for key in ("fetched", "accepted", "owner_review", "quarantined", "rejected", "duplicates", "errors"):
            totals[key] += int(stage_counts.get(key) or 0)
    totals["fetched"] += int(public_result.get("fetched") or 0)
    totals["accepted"] += int(public_result.get("accepted") or 0)
    totals["owner_review"] += int(public_result.get("owner_review") or 0)
    totals["quarantined"] += int(public_result.get("quarantined") or 0)
    totals["rejected"] += int(public_result.get("rejected") or 0)
    totals["duplicates"] += int(public_result.get("duplicates") or 0)
    totals["errors"] += len(public_result.get("source_errors") or [])

    reason_distribution: Counter = Counter()
    for src in public_result.get("sources", []):
        for code, count in (src.get("reason_distribution") or {}).items():
            reason_distribution[code] += int(count)

    return {
        "action": "run_all_discovery",
        "started_at": started.isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
        "actor": actor,
        "stages": {
            "gmail": gmail,
            "public": {
                "attempted": [s for s in public_result.get("sources_attempted", []) if s.get("source_key") not in _ATS_KEYS],
                "skipped": [s for s in public_result.get("sources_skipped", []) if s.get("source_key") not in _ATS_KEYS],
                "sources": public_sources,
            },
            "ats": {
                "attempted": [s for s in public_result.get("sources_attempted", []) if s.get("source_key") in _ATS_KEYS],
                "skipped": [s for s in public_result.get("sources_skipped", []) if s.get("source_key") in _ATS_KEYS],
                "sources": ats_sources,
            },
        },
        "totals": {
            "fetched": totals["fetched"],
            "accepted": totals["accepted"],
            "owner_review": totals["owner_review"],
            "quarantined": totals["quarantined"],
            "rejected": totals["rejected"],
            "duplicates": totals["duplicates"],
            "errors": totals["errors"],
        },
        "reason_distribution": dict(reason_distribution),
        "source_errors": public_result.get("source_errors", []),
        "message": (
            f"Gmail {'skipped:'+str(gmail.get('skip_reason')) if gmail.get('skipped') else 'accepted='+str(gmail.get('accepted'))}; "
            f"public+ats fetched={public_result.get('fetched')} accepted={public_result.get('accepted')} "
            f"owner_review={public_result.get('owner_review')} rejected={public_result.get('rejected')} "
            f"duplicates={public_result.get('duplicates')} errors={totals['errors']}"
        ),
    }
