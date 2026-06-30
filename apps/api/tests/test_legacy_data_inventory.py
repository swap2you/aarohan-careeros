"""Tests for defensible legacy fixture/test classification."""

from fastapi.testclient import TestClient

from app.models import Job
from app.services.legacy_data_inventory import classify_job


def test_e2e_external_id_sets_test_provenance(client: TestClient, auth_headers):
    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "approved_remote_feeds",
            "external_id": "e2e-inventory-001",
            "title": "E2E QE Director",
            "company": "E2E Dup Co",
            "location": "Remote",
            "url": "https://example.com/e2e/dup-001",
            "description_text": "E2E inventory test",
        },
    ).json()
    assert job["data_provenance"] == "test"


def test_fixture_ingest_hidden_from_owner_list(client: TestClient, auth_headers):
    before = client.get("/api/jobs", headers=auth_headers).json()["total"]
    client.post("/api/jobs/ingest/fixture", headers=auth_headers)
    after = client.get("/api/jobs", headers=auth_headers).json()["total"]
    assert after == before


def test_fixture_job_classified_for_cleanup(client: TestClient, auth_headers):
    jobs = client.post("/api/jobs/ingest/fixture", headers=auth_headers).json()
    row = Job(
        id=jobs[0]["id"],
        source=jobs[0]["source"],
        external_id=jobs[0]["external_id"],
        title=jobs[0]["title"],
        company=jobs[0]["company"],
        url=jobs[0]["url"],
        data_provenance=jobs[0]["data_provenance"],
    )
    classified = classify_job(row, e2e_actor_ids=set(), fixture_audit_ids=set())
    assert classified is not None
    assert classified.proposed_provenance == "fixture"
    assert classified.proposed_action == "delete_candidate"


def test_live_job_not_classified_for_deletion(client: TestClient, auth_headers):
    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "manual",
            "external_id": "owner-live-job-001",
            "title": "Director Quality Engineering",
            "company": "Real Employer Inc",
            "location": "Remote",
            "url": "https://careers.real-employer.com/jobs/001",
            "description_text": "Lead quality engineering.",
        },
    ).json()
    row = Job(
        id=job["id"],
        source=job["source"],
        external_id=job["external_id"],
        title=job["title"],
        company=job["company"],
        url=job["url"],
        data_provenance=job.get("data_provenance", "live"),
    )
    assert classify_job(row, e2e_actor_ids=set(), fixture_audit_ids=set()) is None
