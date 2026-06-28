from unittest.mock import patch

from fastapi.testclient import TestClient


def test_list_connectors(client: TestClient, auth_headers):
    response = client.get("/api/connectors", headers=auth_headers)
    assert response.status_code == 200
    connectors = {c["provider_id"]: c for c in response.json()["connectors"]}
    assert connectors["greenhouse"]["state"] == "READY"
    assert connectors["adzuna"]["state"] == "NOT_CONFIGURED"
    assert connectors["jooble"]["state"] == "NOT_CONFIGURED"
    assert connectors["usajobs"]["state"] == "NOT_CONFIGURED"
    assert connectors["fixture"]["state"] == "READY"


def test_fixture_connector_run(client: TestClient, auth_headers):
    response = client.post(
        "/api/connectors/fixture/run",
        headers=auth_headers,
        json={"use_fixture": True, "params": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ingested"] >= 1
    assert body["fixture"] is True


def test_not_configured_connector_returns_message(client: TestClient, auth_headers):
    response = client.post(
        "/api/connectors/adzuna/run",
        headers=auth_headers,
        json={"use_fixture": False, "params": {"what": "qa director"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "NOT_CONFIGURED"
    assert body["ingested"] == 0


def test_adzuna_fixture_run(client: TestClient, auth_headers):
    response = client.post(
        "/api/connectors/adzuna/run",
        headers=auth_headers,
        json={"use_fixture": True},
    )
    assert response.status_code == 200
    assert response.json()["ingested"] >= 1


def test_all_public_fixtures_ingest(client: TestClient, auth_headers):
    for provider_id in ["ashby", "remotive", "remote_ok", "rss", "jooble", "usajobs", "greenhouse", "lever"]:
        response = client.post(
            f"/api/connectors/{provider_id}/run",
            headers=auth_headers,
            json={"use_fixture": True},
        )
        assert response.status_code == 200, provider_id
        assert response.json()["ingested"] >= 1, provider_id


def test_greenhouse_live_fetch_mocked(client: TestClient, auth_headers):
    mock_jobs = {
        "jobs": [
            {
                "id": 999,
                "title": "Mock QE Director",
                "location": {"name": "Remote"},
                "content": "<p>Mock description</p>",
                "absolute_url": "https://example.com/gh/mock",
                "updated_at": "2026-06-01T00:00:00Z",
            }
        ]
    }
    with patch("app.integrations.job_providers._http_get", return_value=mock_jobs):
        response = client.post(
            "/api/connectors/greenhouse/run",
            headers=auth_headers,
            json={"use_fixture": False, "params": {"board_token": "mock-board"}},
        )
    assert response.status_code == 200
    assert response.json()["ingested"] == 1


def test_unknown_connector_404(client: TestClient, auth_headers):
    response = client.post(
        "/api/connectors/unknown/run",
        headers=auth_headers,
        json={"use_fixture": True},
    )
    assert response.status_code == 404
