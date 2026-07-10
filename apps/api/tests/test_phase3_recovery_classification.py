"""Phase 3 recovery row classification tests."""

from __future__ import annotations

from app.models import Job, User
from app.services.recovery_row_classification import (
    CLASS_EXCLUDE,
    CLASS_FIXTURE,
    CLASS_LIVE_RECONSTRUCT,
    CLASS_OWNER_CONFIRMED,
    CLASS_SYSTEM_REQUIRED,
    CLASS_TEST,
    classify_job_row,
    classify_user,
)


def test_e2e_user_excluded():
    user = User(id=1, email="e2e@test.local", hashed_password="x", is_active=True, is_admin=False)
    result = classify_user(user)
    assert result.classification == CLASS_EXCLUDE


def test_owner_user_system_required():
    user = User(id=2, email="owner@example.com", hashed_password="x", is_active=True, is_admin=True)
    result = classify_user(user)
    assert result.classification == CLASS_SYSTEM_REQUIRED


def test_pg_test_job_excluded():
    job = Job(
        id=1,
        source="approved_remote_feeds",
        external_id="pg-1",
        title="Director",
        company="PG Test Co 8904a282",
        url="https://example.com/1",
        description_html="",
        description_text="",
        dedupe_key="k1",
    )
    result = classify_job_row(job, e2e_actor_ids=set(), fixture_audit_ids=set(), application_job_ids=set())
    assert result.classification == CLASS_EXCLUDE


def test_gmail_job_reconstructable():
    job = Job(
        id=2,
        source="linkedin_alert_emails",
        external_id="li-1",
        title="Director QE",
        company="Acme Corp",
        url="https://linkedin.com/jobs/1",
        description_html="",
        description_text="US remote",
        dedupe_key="k2",
    )
    result = classify_job_row(job, e2e_actor_ids=set(), fixture_audit_ids=set(), application_job_ids=set())
    assert result.classification == CLASS_LIVE_RECONSTRUCT


def test_manual_job_owner_confirmed():
    job = Job(
        id=3,
        source="manual",
        external_id="m-1",
        title="Director QE",
        company="Real Co",
        url="https://careers.real.com/1",
        description_html="",
        description_text="",
        dedupe_key="k3",
    )
    result = classify_job_row(
        job, e2e_actor_ids=set(), fixture_audit_ids=set(), application_job_ids={3}
    )
    assert result.classification == CLASS_OWNER_CONFIRMED


def test_e2e_company_test():
    job = Job(
        id=4,
        source="approved_remote_feeds",
        external_id="e2e-dup",
        title="QE",
        company="E2E Dup Co",
        url="https://example.com/e2e/dup",
        description_html="",
        description_text="",
        dedupe_key="k4",
    )
    result = classify_job_row(job, e2e_actor_ids=set(), fixture_audit_ids=set(), application_job_ids=set())
    assert result.classification == CLASS_TEST


def test_example_health_fixture():
    job = Job(
        id=5,
        source="approved_remote_feeds",
        external_id="ex-1",
        title="Director",
        company="Example Health Tech",
        url="https://example.com/5",
        description_html="",
        description_text="",
        dedupe_key="k5",
    )
    result = classify_job_row(job, e2e_actor_ids=set(), fixture_audit_ids=set(), application_job_ids=set())
    assert result.classification == CLASS_FIXTURE
