"""Job detail API and null-safe rendering tests."""

from fastapi.testclient import TestClient


def test_job_detail_with_null_description(client: TestClient, auth_headers):
    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "manual",
            "external_id": "detail-null-desc",
            "title": "QA Lead",
            "company": "Acme Corp",
            "url": "https://boards.greenhouse.io/acme/jobs/123",
            "description_text": None,
            "description_html": "",
        },
    ).json()
    response = client.get(f"/api/jobs/{job['id']}/detail", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["job"]["title"] == "QA Lead"
    assert isinstance(body["job"]["description_text"], str)
    assert body["duplicate_risk"]["level"] in {"GREEN", "AMBER", "RED"}


def test_job_detail_not_found(client: TestClient, auth_headers):
    response = client.get("/api/jobs/999999/detail", headers=auth_headers)
    assert response.status_code == 404


def test_jobs_list_excludes_fixture_by_default(client: TestClient, auth_headers):
    client.post("/api/jobs/ingest/fixture", headers=auth_headers)
    client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "manual",
            "external_id": "owner-visible-job",
            "title": "Owner Job",
            "company": "Real Co",
            "url": "https://jobs.lever.co/real/abc",
            "description_text": "Real description",
        },
    )
    listed = client.get("/api/jobs", headers=auth_headers).json()
    titles = [item["title"] for item in listed["items"]]
    assert "Owner Job" in titles
    assert all(item.get("data_provenance") not in {"fixture", "test"} for item in listed["items"])
