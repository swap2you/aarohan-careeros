"""Workflow 01.5 — canonical origin classification and manual-opportunity protection."""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job, JobOrigin, ManualOpportunityStatus, WorkflowState
from app.routers.jobs import _apply_fresh_jobs_defaults, _owner_jobs_query
from app.services.discovery_origin import (
    backfill_origins,
    classify_origin,
    is_manual_opportunity,
    mark_owner_added,
    set_manual_status,
)


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
        "source": "jooble",
        "external_id": "o-1",
        "title": "QE Manager",
        "company": "Acme",
        "url": "https://example.com/jobs/1",
        "description_html": "",
        "description_text": "software quality",
        "dedupe_key": "o-1",
        "data_provenance": "live",
        "discovered_at": datetime.utcnow(),
        "effective_freshness_at": datetime.utcnow(),
        "eligible_for_owner": True,
        "ingest_decision": "ACCEPT",
        "state": WorkflowState.NORMALIZED.value,
    }
    defaults.update(kwargs)
    job = Job(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_classify_origin_categories():
    assert classify_origin(source="manual", data_provenance="manual") == JobOrigin.OWNER_ADDED.value
    assert classify_origin(source="gmail", data_provenance="gmail") == JobOrigin.GMAIL_ALERT.value
    assert classify_origin(source="greenhouse", data_provenance="connector") == JobOrigin.ATS_BOARD.value
    assert classify_origin(source="jooble", data_provenance="live") == JobOrigin.PUBLIC_CONNECTOR.value
    assert classify_origin(source="gmail", data_provenance="gmail", message_type="RECRUITER") == JobOrigin.RECRUITER_MESSAGE.value


def test_backfill_origins_is_idempotent():
    db = _session()
    try:
        _add_job(db, external_id="g", dedupe_key="g", source="gmail", data_provenance="gmail", origin=None)
        _add_job(db, external_id="p", dedupe_key="p", source="jooble", data_provenance="live", origin=None)
        counts = backfill_origins(db)
        assert counts.get(JobOrigin.GMAIL_ALERT.value) == 1
        assert counts.get(JobOrigin.PUBLIC_CONNECTOR.value) == 1
        assert backfill_origins(db) == {}
    finally:
        db.close()


def test_mark_owner_added_sets_protection_and_status():
    db = _session()
    try:
        job = _add_job(db, external_id="m", dedupe_key="m")
        mark_owner_added(job, added_by="owner@test")
        db.commit()
        assert job.origin == JobOrigin.OWNER_ADDED.value
        assert job.manual_protected is True
        assert job.owner_confirmed is True
        assert job.manual_status == ManualOpportunityStatus.SAVED.value
        assert is_manual_opportunity(job)
    finally:
        db.close()


def test_set_manual_status_applied_protects_from_ageout():
    db = _session()
    try:
        job = _add_job(db, external_id="s", dedupe_key="s")
        set_manual_status(job, ManualOpportunityStatus.APPLIED.value)
        db.commit()
        assert job.manual_status == "APPLIED"
        assert job.manual_protected is True
    finally:
        db.close()


def _fresh_ids(db):
    query = _apply_fresh_jobs_defaults(
        _owner_jobs_query(db),
        max_age_hours=None,
        eligibility=None,
        include_archived=False,
        include_quarantined=False,
        recommended_profile=None,
        country_eligibility=None,
        relax_fresh_defaults=False,
    )
    return {j.id for j in query.all()}


def test_manual_protected_opportunity_survives_freshness_ageout():
    db = _session()
    try:
        stale = datetime.utcnow() - timedelta(days=90)
        job = _add_job(
            db,
            external_id="old-manual",
            dedupe_key="old-manual",
            data_provenance="manual",
            origin=JobOrigin.OWNER_ADDED.value,
            manual_protected=True,
            manual_status=ManualOpportunityStatus.SAVED.value,
            effective_freshness_at=stale,
            state=WorkflowState.NORMALIZED.value,
        )
        # A stale non-protected connector job is hidden; the protected manual one is visible.
        aged_connector = _add_job(
            db,
            external_id="old-conn",
            dedupe_key="old-conn",
            effective_freshness_at=stale,
        )
        ids = _fresh_ids(db)
        assert job.id in ids
        assert aged_connector.id not in ids
    finally:
        db.close()
