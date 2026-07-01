"""Apply readiness endpoint regression."""

from fastapi.testclient import TestClient


def test_apply_readiness_after_fixture_ingest(client: TestClient, auth_headers):
    job = client.post("/api/jobs/ingest/fixture", headers=auth_headers).json()[0]
    response = client.get(f"/api/applications/jobs/{job['id']}/apply-readiness", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["official_url"]
    assert "not submitted" in body["message"].lower()
