"""Run job discovery connectors with eligibility gates and persisted run history."""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from app.integrations.job_providers import ConnectorState, FetchResult, get_provider
from app.models import ConnectorRun
from app.services.audit import write_audit
from app.services.ingestion import ingest_job_with_decision
from app.services.job_eligibility import (
    DECISION_ACCEPT,
    DECISION_DUPLICATE,
    DECISION_HISTORICAL,
    DECISION_OWNER_REVIEW,
    DECISION_QUARANTINE,
    DECISION_REJECT,
    DECISION_SECONDARY,
)

# In-memory cache still used for fast status; DB is source of truth.
_last_runs: dict[str, dict] = {}


def record_run(provider_id: str, *, job_count: int, fixture: bool, health_state: str | None = None) -> None:
    _last_runs[provider_id] = {
        "last_run_at": datetime.utcnow(),
        "last_job_count": job_count,
        "fixture": fixture,
        "health_state": health_state,
    }


def last_run(provider_id: str) -> dict | None:
    return _last_runs.get(provider_id)


def latest_db_run(db: Session, provider_id: str) -> ConnectorRun | None:
    return (
        db.query(ConnectorRun)
        .filter(ConnectorRun.provider == provider_id)
        .order_by(ConnectorRun.started_at.desc())
        .first()
    )


def probe_connector_health(provider_id: str, db: Session | None = None) -> dict:
    """Health semantics: HEALTHY only after a successful live run with fetched records."""
    t0 = time.perf_counter()
    try:
        provider = get_provider(provider_id)
        status = provider.base_status()
        error = None
        record_count = 0
        mapped = "NOT_CONFIGURED"

        if status.state == ConnectorState.DISABLED:
            mapped = "DISABLED"
            error = status.message or "disabled"
        elif status.state == ConnectorState.NOT_CONFIGURED:
            mapped = "NOT_CONFIGURED"
            error = "not configured"
        elif status.state == ConnectorState.READY:
            mapped = "CONFIGURED"
            db_run = latest_db_run(db, provider_id) if db is not None else None
            if db_run and db_run.live and not db_run.error_redacted and db_run.fetched_count > 0:
                mapped = "HEALTHY"
                record_count = db_run.fetched_count
            elif db_run and db_run.error_redacted:
                mapped = "ERROR"
                error = db_run.error_redacted
                record_count = db_run.fetched_count
            elif db_run and db_run.fetched_count == 0 and not db_run.error_redacted:
                mapped = "DEGRADED"
                error = "live run returned zero records"
            else:
                mapped = "CONFIGURED"
                error = "configured but never successfully run live"
        else:
            mapped = "DEGRADED"
            error = status.message

        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "status": mapped,
            "record_count": record_count,
            "latency_ms": latency_ms,
            "error": error,
        }
    except KeyError:
        return {"status": "ERROR", "record_count": 0, "latency_ms": 0, "error": "unknown provider"}
    except Exception as exc:
        return {
            "status": "ERROR",
            "record_count": 0,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error": str(exc)[:120],
        }


def run_connector(
    db: Session,
    provider_id: str,
    *,
    actor: str,
    use_fixture: bool = False,
    params: dict | None = None,
    persist_rejects: bool = True,
) -> dict:
    provider = get_provider(provider_id)
    status = provider.base_status()
    started = datetime.utcnow()
    t0 = time.perf_counter()
    search_profile = {"provider_id": provider_id, "params": params or {}, "fixture": use_fixture}

    if use_fixture:
        jobs = provider.fixture_jobs()
        result = FetchResult(jobs=jobs, provenance={"fixture": True, "provider": provider_id})
    else:
        if status.state == ConnectorState.NOT_CONFIGURED:
            return {
                "provider_id": provider_id,
                "state": status.state.value,
                "health_state": "NOT_CONFIGURED",
                "ingested": 0,
                "fetched": 0,
                "accepted": 0,
                "secondary_review": 0,
                "quarantined": 0,
                "rejected": 0,
                "duplicates": 0,
                "message": status.message,
            }
        if status.state == ConnectorState.DISABLED:
            return {
                "provider_id": provider_id,
                "state": status.state.value,
                "health_state": "DISABLED",
                "ingested": 0,
                "fetched": 0,
                "accepted": 0,
                "secondary_review": 0,
                "quarantined": 0,
                "rejected": 0,
                "duplicates": 0,
                "message": status.message,
            }
        try:
            result = provider.fetch_jobs(**(params or {}))
        except ValueError as exc:
            return {
                "provider_id": provider_id,
                "state": status.state.value,
                "health_state": "ERROR",
                "ingested": 0,
                "fetched": 0,
                "accepted": 0,
                "secondary_review": 0,
                "quarantined": 0,
                "rejected": 0,
                "duplicates": 0,
                "message": str(exc),
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            err = str(exc)[:240]
            run = ConnectorRun(
                provider=provider_id,
                started_at=started,
                completed_at=datetime.utcnow(),
                search_profile=search_profile,
                fetched_count=0,
                latency_ms=latency_ms,
                error_redacted=err,
                live=not use_fixture,
                health_state="ERROR",
                actor=actor,
            )
            db.add(run)
            db.commit()
            return {
                "provider_id": provider_id,
                "state": status.state.value,
                "health_state": "ERROR",
                "ingested": 0,
                "fetched": 0,
                "accepted": 0,
                "secondary_review": 0,
                "quarantined": 0,
                "rejected": 0,
                "duplicates": 0,
                "message": err,
                "run_id": run.id,
            }

    counts = Counter()
    reason_counts: Counter = Counter()
    job_ids: list[int] = []
    for item in result.jobs:
        if use_fixture:
            item = {**item, "data_provenance": item.get("data_provenance") or "fixture"}
        else:
            item = {**item, "data_provenance": item.get("data_provenance") or "connector"}
        outcome = ingest_job_with_decision(
            db,
            item,
            actor=actor,
            skip_eligibility=use_fixture,
            persist_rejects=persist_rejects,
        )
        counts[outcome.decision] += 1
        for code in outcome.reason_codes or []:
            reason_counts[code] += 1
        if outcome.job:
            job_ids.append(outcome.job.id)

    accepted = counts[DECISION_ACCEPT]
    secondary = counts[DECISION_SECONDARY] + counts[DECISION_OWNER_REVIEW]
    owner_review = counts[DECISION_OWNER_REVIEW] + counts[DECISION_SECONDARY]
    quarantined = counts[DECISION_QUARANTINE]
    rejected = counts[DECISION_REJECT] + counts[DECISION_HISTORICAL]
    duplicates = counts[DECISION_DUPLICATE]
    fetched = len(result.jobs)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    health_state = "HEALTHY" if (not use_fixture and fetched > 0) else ("DEGRADED" if not use_fixture else "CONFIGURED")
    if use_fixture:
        health_state = "CONFIGURED"

    run = ConnectorRun(
        provider=provider_id,
        started_at=started,
        completed_at=datetime.utcnow(),
        search_profile=search_profile,
        fetched_count=fetched,
        accepted_count=accepted,
        secondary_review_count=secondary,
        quarantined_count=quarantined,
        rejected_count=rejected,
        duplicate_count=duplicates,
        archived_count=0,
        latency_ms=latency_ms,
        error_redacted=None,
        live=not use_fixture,
        health_state=health_state,
        reason_distribution=dict(reason_counts),
        actor=actor,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    record_run(provider_id, job_count=fetched, fixture=use_fixture, health_state=health_state)
    write_audit(
        db,
        event_type="connector.run",
        actor=actor,
        resource_type="connector",
        resource_id=provider_id,
        details={
            "provider": provider_id,
            "job_count": fetched,
            "accepted": accepted,
            "secondary_review": secondary,
            "quarantined": quarantined,
            "rejected": rejected,
            "duplicates": duplicates,
            "fixture": use_fixture,
            "provenance": result.provenance,
            "run_id": run.id,
            "health_state": health_state,
        },
    )
    return {
        "provider_id": provider_id,
        "state": status.state.value,
        "health_state": health_state,
        "ingested": accepted + secondary + quarantined,
        "fetched": fetched,
        "accepted": accepted,
        "owner_review": owner_review,
        "secondary_review": secondary,
        "quarantined": quarantined,
        "rejected": rejected,
        "duplicates": duplicates,
        "job_ids": job_ids,
        "provenance": result.provenance,
        "fixture": use_fixture,
        "run_id": run.id,
        "reason_distribution": dict(reason_counts),
    }
