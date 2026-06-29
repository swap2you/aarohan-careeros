"""Tests for application list enrichment."""

from fastapi.testclient import TestClient


def test_applications_list_includes_job_context(client: TestClient, auth_headers):
    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "manual",
            "external_id": "app-summary-job",
            "title": "Senior QA Engineer",
            "company": "Acme Corp",
            "url": "https://example.com/jobs/1",
            "description_text": "Lead quality engineering.",
        },
    ).json()
    client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers)
    response = client.get("/api/applications", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    item = next(i for i in body["items"] if i["job_id"] == job["id"])
    assert item["job_title"] == "Senior QA Engineer"
    assert item["company_name"] == "Acme Corp"
    assert item["official_url"] == "https://example.com/jobs/1"
    assert item["packet_version"] is not None
