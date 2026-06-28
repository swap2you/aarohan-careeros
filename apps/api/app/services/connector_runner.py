"""Run job discovery connectors and record health."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.integrations.job_providers import ConnectorState, FetchResult, get_provider
from app.services.audit import write_audit
from app.services.ingestion import ingest_job

_last_runs: dict[str, dict] = {}


def record_run(provider_id: str, *, job_count: int, fixture: bool) -> None:
    _last_runs[provider_id] = {
        "last_run_at": datetime.utcnow(),
        "last_job_count": job_count,
        "fixture": fixture,
    }


def last_run(provider_id: str) -> dict | None:
    return _last_runs.get(provider_id)


def run_connector(
    db: Session,
    provider_id: str,
    *,
    actor: str,
    use_fixture: bool = False,
    params: dict | None = None,
) -> dict:
    provider = get_provider(provider_id)
    status = provider.base_status()
    if use_fixture:
        jobs = provider.fixture_jobs()
        result = FetchResult(jobs=jobs, provenance={"fixture": True, "provider": provider_id})
    else:
        if status.state == ConnectorState.NOT_CONFIGURED:
            return {
                "provider_id": provider_id,
                "state": status.state.value,
                "ingested": 0,
                "message": status.message,
            }
        if status.state == ConnectorState.DISABLED:
            return {
                "provider_id": provider_id,
                "state": status.state.value,
                "ingested": 0,
                "message": status.message,
            }
        result = provider.fetch_jobs(**(params or {}))

    ingested = []
    for item in result.jobs:
        ingested.append(ingest_job(db, item, actor=actor))

    record_run(provider_id, job_count=len(ingested), fixture=use_fixture)
    write_audit(
        db,
        event_type="connector.run",
        actor=actor,
        resource_type="connector",
        resource_id=provider_id,
        details={
            "job_count": len(ingested),
            "fixture": use_fixture,
            "provenance": result.provenance,
        },
    )
    return {
        "provider_id": provider_id,
        "state": status.state.value,
        "ingested": len(ingested),
        "job_ids": [job.id for job in ingested],
        "provenance": result.provenance,
        "fixture": use_fixture,
    }
