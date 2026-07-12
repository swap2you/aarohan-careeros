"""Discovery source inventory (Workflow 01.5, Section 2).

Produces a complete, owner-facing inventory across three source classes:
- Email alert sources (LinkedIn / Indeed / Dice / USAJOBS / Glassdoor / other recruiter alerts)
  — these are **not public-feed connectors**; they are orchestrated via Gmail discovery.
- Public / API sources (Adzuna, Jooble, USAJOBS, Remotive, Remote OK, RSS).
- ATS sources (Greenhouse, Lever, Ashby) — enabled but require explicit approved boards.

Per source it reports policy/config/credential state, OAuth/access health, last attempted /
successful run, and the decision-count distribution from the most recent connector run.
No secrets or tokens are included.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConnectorRun, OAuthToken
from app.services.discovery_policy import job_discovery_policy

EMAIL_ALERT_SOURCES = {
    "linkedin_alert_emails": "LinkedIn",
    "indeed_alert_emails": "Indeed",
    "dice_alert_emails": "Dice",
    "usajobs_alert_emails": "USAJOBS",
    "glassdoor_alert_emails": "Glassdoor",
}
PUBLIC_SOURCES = {"adzuna", "jooble", "usajobs", "remotive", "remote_ok", "rss"}
ATS_SOURCES = {"greenhouse", "lever", "ashby"}


def _latest_run(db: Session, provider_id: str) -> ConnectorRun | None:
    return db.execute(
        select(ConnectorRun)
        .where(ConnectorRun.provider == provider_id)
        .order_by(ConnectorRun.started_at.desc())
    ).scalars().first()


def _latest_successful_run(db: Session, provider_id: str) -> ConnectorRun | None:
    return db.execute(
        select(ConnectorRun)
        .where(ConnectorRun.provider == provider_id)
        .where(ConnectorRun.completed_at.is_not(None))
        .where(ConnectorRun.health_state != "ERROR")
        .order_by(ConnectorRun.started_at.desc())
    ).scalars().first()


def _run_counts(run: ConnectorRun | None) -> dict:
    if run is None:
        return {
            "fetched": None,
            "accepted": None,
            "owner_review": None,
            "quarantined": None,
            "rejected": None,
            "duplicate": None,
            "archived": None,
            "parser_failures": None,
            "provider_failures": None,
            "reason_distribution": {},
        }
    reason = run.reason_distribution or {}
    parser_failures = int(reason.get("PARSER_FAILURE", 0)) if isinstance(reason, dict) else 0
    provider_failures = 1 if run.health_state == "ERROR" else 0
    return {
        "fetched": run.fetched_count,
        "accepted": run.accepted_count,
        "owner_review": run.secondary_review_count,
        "quarantined": run.quarantined_count,
        "rejected": run.rejected_count,
        "duplicate": run.duplicate_count,
        "archived": run.archived_count,
        "parser_failures": parser_failures,
        "provider_failures": provider_failures,
        "reason_distribution": reason if isinstance(reason, dict) else {},
    }


def _gmail_health(db: Session) -> dict:
    tokens = db.execute(
        select(OAuthToken).where(OAuthToken.provider == "google", OAuthToken.is_active.is_(True))
    ).scalars().all()
    gmail_tokens = [t for t in tokens if (t.service or "").lower() in {"gmail", "unified", "google"}]
    account = next((t.account_email for t in gmail_tokens if t.account_email), None)
    return {
        "credentials_present": bool(gmail_tokens),
        "oauth_health": "ACTIVE" if gmail_tokens else "NOT_CONNECTED",
        "account_email": account,
        "active_token_count": len(gmail_tokens),
    }


def build_source_inventory(db: Session) -> dict:
    """Build the full discovery source inventory."""
    from app.integrations.job_providers import get_provider

    policy = job_discovery_policy()
    sources_cfg = policy.get("sources", {})
    gmail_health = _gmail_health(db)

    email_alerts: list[dict] = []
    for key, label in EMAIL_ALERT_SOURCES.items():
        cfg = sources_cfg.get(key, {})
        enabled = bool(cfg.get("enabled")) if isinstance(cfg, dict) else False
        email_alerts.append(
            {
                "source_key": key,
                "label": label,
                "class": "email_alert",
                "connector_kind": "not_a_public_feed_connector",
                "enabled_in_policy": enabled,
                "technically_configured": gmail_health["credentials_present"],
                "credentials_present": gmail_health["credentials_present"],
                "oauth_health": gmail_health["oauth_health"],
                "account_email": gmail_health["account_email"],
                "orchestration": "gmail_discovery",
                "skip_reason": None if enabled else "disabled_in_policy",
                "note": "Gmail job alerts are ingested via Gmail discovery, not a public feed.",
            }
        )

    def _provider_entry(key: str, source_class: str) -> dict:
        cfg = sources_cfg.get(key, {}) if isinstance(sources_cfg.get(key), dict) else {}
        enabled = bool(cfg.get("enabled"))
        provider_id = cfg.get("provider_id", key)
        entry: dict = {
            "source_key": key,
            "label": key.replace("_", " ").title(),
            "class": source_class,
            "connector_kind": "public_feed_connector" if source_class == "public" else "ats_board",
            "provider_id": provider_id,
            "enabled_in_policy": enabled,
        }
        try:
            provider = get_provider(provider_id)
            status = provider.base_status()
            configured = provider.is_configured()
            entry.update(
                {
                    "technically_configured": configured,
                    "credentials_present": (not status.requires_api_key) or configured,
                    "requires_api_key": status.requires_api_key,
                    "connector_state": status.state.value,
                    "oauth_health": "N/A",
                }
            )
        except Exception as exc:  # provider not registered / unavailable
            entry.update(
                {
                    "technically_configured": False,
                    "credentials_present": False,
                    "requires_api_key": None,
                    "connector_state": "UNAVAILABLE",
                    "oauth_health": "N/A",
                    "provider_error": str(exc)[:160],
                }
            )

        last = _latest_run(db, provider_id)
        last_success = _latest_successful_run(db, provider_id)
        entry["last_attempted_run"] = last.started_at.isoformat() if last and last.started_at else None
        entry["last_successful_run"] = (
            last_success.started_at.isoformat() if last_success and last_success.started_at else None
        )
        entry["last_run_health"] = last.health_state if last else None
        entry["last_run_counts"] = _run_counts(last)

        if source_class == "ats":
            boards = cfg.get("approved_boards") or []
            entry["approved_boards_count"] = len(boards)
            entry["approved_boards"] = list(boards)
            if enabled and not boards:
                entry["skip_reason"] = "enabled_no_approved_boards"
            elif not enabled:
                entry["skip_reason"] = "disabled_in_policy"
            else:
                entry["skip_reason"] = None
        else:
            if not enabled:
                entry["skip_reason"] = "disabled_in_policy"
            elif entry.get("requires_api_key") and not entry.get("technically_configured"):
                entry["skip_reason"] = "credentials_not_configured"
            elif entry.get("connector_state") == "DISABLED":
                entry["skip_reason"] = "blocked_by_source_policy"
            else:
                entry["skip_reason"] = None
        return entry

    public = [_provider_entry(key, "public") for key in sorted(PUBLIC_SOURCES)]
    ats = [_provider_entry(key, "ats") for key in sorted(ATS_SOURCES)]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "gmail_integration": gmail_health,
        "email_alert_sources": email_alerts,
        "public_sources": public,
        "ats_sources": ats,
        "summary": {
            "email_alert_enabled": sum(1 for e in email_alerts if e["enabled_in_policy"]),
            "public_ready": sum(1 for p in public if p.get("skip_reason") is None),
            "public_skipped": sum(1 for p in public if p.get("skip_reason")),
            "ats_with_boards": sum(1 for a in ats if a.get("approved_boards_count")),
        },
    }
