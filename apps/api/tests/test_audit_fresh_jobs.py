"""Unit tests for Fresh Jobs audit runner (in-memory DB; no Docker required)."""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job, WorkflowState
from scripts.audit_fresh_jobs import CONFIRMATION_PHRASE, _redact_secrets, run_audit, summary_from_report


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _add_job(db, **kwargs):
    defaults = {
        "source": "approved_remote_feeds",
        "external_id": "audit-1",
        "title": "Director of Quality Engineering",
        "company": "Acme",
        "location": "Remote, United States",
        "url": "https://example.com/jobs/1",
        "description_html": "",
        "description_text": "US remote quality leadership",
        "dedupe_key": "k1",
        "state": WorkflowState.NORMALIZED.value,
        "data_provenance": "live",
        "discovered_at": datetime.utcnow(),
        "posted_at": datetime.utcnow(),
        "provider_posted_at": datetime.utcnow(),
        "effective_freshness_at": datetime.utcnow(),
        "eligible_for_owner": True,
        "is_archived": False,
    }
    defaults.update(kwargs)
    job = Job(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_dry_run_performs_no_writes():
    db = _session()
    try:
        _add_job(db, external_id="dry-1", dedupe_key="dry-1", url="https://example.com/dry-1")
        before = [
            (j.id, j.state, j.is_archived, j.eligible_for_owner, j.ingest_decision)
            for j in db.query(Job).all()
        ]
        report = run_audit(db, execute=False)
        assert report["mode"] == "dry_run"
        assert report["records_updated"] == 0
        assert report["total_owner_jobs"] == 1
        after = [
            (j.id, j.state, j.is_archived, j.eligible_for_owner, j.ingest_decision)
            for j in db.query(Job).all()
        ]
        assert before == after
        summary = summary_from_report(report)
        assert "records_updated" not in summary
    finally:
        db.close()


def test_wrong_confirmation_performs_no_writes():
    db = _session()
    try:
        _add_job(
            db,
            external_id="bad-confirm",
            dedupe_key="bad-confirm",
            url="https://example.com/bad-confirm",
            title="Backend Engineer",
            location="Bangalore, India",
            description_text="India only backend role",
        )
        before = [(j.id, j.state, j.is_archived, j.eligible_for_owner) for j in db.query(Job).all()]
        report = run_audit(db, execute=True, confirmation_text="WRONG PHRASE")
        assert report["mode"] == "execute_blocked"
        assert report["records_updated"] == 0
        assert "ConfirmationText mismatch" in report["execute_error"]
        after = [(j.id, j.state, j.is_archived, j.eligible_for_owner) for j in db.query(Job).all()]
        assert before == after
    finally:
        db.close()


def test_execute_uses_exact_confirmation_and_never_deletes():
    db = _session()
    try:
        job = _add_job(
            db,
            external_id="exec-1",
            dedupe_key="exec-1",
            url="https://example.com/exec-1",
            title="Manual Tester",
            location="Remote, Canada",
            description_text="Canada only manual tester",
        )
        report = run_audit(db, execute=True, confirmation_text=CONFIRMATION_PHRASE)
        assert report["mode"] == "execute"
        assert db.query(Job).filter(Job.id == job.id).count() == 1
        refreshed = db.query(Job).filter(Job.id == job.id).one()
        # Must still exist; may be archived/rejected/quarantined depending on gates
        assert refreshed.id == job.id
    finally:
        db.close()


def test_redact_secrets_helper():
    raw = "Could not parse postgresql+psycopg://career_os:SuperSecret@postgres:5432/career_os"
    scrubbed = _redact_secrets(raw)
    assert "SuperSecret" not in scrubbed
    assert "postgresql://" in scrubbed


def test_confirmation_phrase_constant():
    assert CONFIRMATION_PHRASE == "ARCHIVE STALE AND INELIGIBLE JOBS"
