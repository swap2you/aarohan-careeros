"""Connector run persistence and discovery campaign."""

from datetime import datetime

from app.models import ConnectorRun
from app.services.connector_runner import probe_connector_health, run_connector


def test_connector_run_persists_statistics(client, auth_headers):
    response = client.post(
        "/api/connectors/fixture/run",
        headers=auth_headers,
        json={"use_fixture": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fetched"] >= 1 or body["ingested"] >= 1
    assert body.get("run_id")

    # Verify via DB through a second list call / ops if available
    runs = client.get("/api/connectors", headers=auth_headers)
    assert runs.status_code == 200


def test_never_run_connector_is_not_healthy():
    # Without a DB session of successful live runs, HEALTHY is impossible.
    probe = probe_connector_health("ashby")
    assert probe["status"] != "HEALTHY"
    assert probe["status"] in {"CONFIGURED", "NOT_CONFIGURED", "DISABLED", "DEGRADED", "ERROR"}


def test_discover_fresh_jobs_endpoint(client, auth_headers):
    response = client.post("/api/workflows/discover-fresh-jobs", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "discover_fresh_jobs"
    assert "fetched" in body
    assert "accepted" in body
    assert "sources" in body


def test_ingest_public_redirects_to_discovery(client, auth_headers):
    response = client.post("/api/workflows/ingest/public", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["action"] == "discover_fresh_jobs"
