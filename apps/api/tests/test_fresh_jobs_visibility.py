"""Workflow Lock 01 — owner Fresh Jobs visibility is governed by eligibility, not by the
lifecycle `state` field.

Regression for the stale-state defect where fit/trust scoring wrote a REJECTED value into
`state`, and the Fresh Jobs read path then hid owner-eligible jobs. The read path must show
any eligible_for_owner + ingest_decision=ACCEPT job regardless of a stale terminal `state`,
and must still hide genuinely ineligible jobs.
"""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job, WorkflowState
from app.routers.jobs import _apply_fresh_jobs_defaults, _owner_jobs_query


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _add_job(db, **kwargs):
    defaults = {
        "source": "approved_remote_feeds",
        "external_id": "vis-1",
        "title": "Senior Manager, Quality Engineering",
        "company": "Acme",
        "location": "Remote, United States",
        "url": "https://example.com/jobs/1",
        "description_html": "",
        "description_text": "US remote software quality leadership",
        "dedupe_key": "vis-1",
        "data_provenance": "live",
        "discovered_at": datetime.utcnow(),
        "posted_at": datetime.utcnow(),
        "provider_posted_at": datetime.utcnow(),
        "effective_freshness_at": datetime.utcnow(),
        "eligible_for_owner": True,
        "ingest_decision": "ACCEPT",
        "is_archived": False,
        "is_expired": False,
        "state": WorkflowState.NORMALIZED.value,
    }
    defaults.update(kwargs)
    job = Job(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _fresh_jobs(db):
    query = _owner_jobs_query(db)
    query = _apply_fresh_jobs_defaults(
        query,
        max_age_hours=None,
        eligibility=None,
        include_archived=False,
        include_quarantined=False,
        recommended_profile=None,
        country_eligibility=None,
        relax_fresh_defaults=False,
    )
    return {j.id for j in query.all()}


def test_eligible_job_with_stale_rejected_state_is_visible():
    db = _session()
    try:
        job = _add_job(
            db,
            external_id="stale-rejected",
            dedupe_key="stale-rejected",
            state=WorkflowState.REJECTED.value,  # legacy fit-derived stale value
        )
        assert job.id in _fresh_jobs(db)
    finally:
        db.close()


def test_ineligible_job_stays_hidden():
    db = _session()
    try:
        job = _add_job(
            db,
            external_id="ineligible",
            dedupe_key="ineligible",
            eligible_for_owner=False,
            ingest_decision="REJECT",
            state=WorkflowState.REJECTED.value,
        )
        assert job.id not in _fresh_jobs(db)
    finally:
        db.close()


def test_eligible_normalized_job_is_visible():
    db = _session()
    try:
        job = _add_job(db, external_id="normal", dedupe_key="normal")
        assert job.id in _fresh_jobs(db)
    finally:
        db.close()
