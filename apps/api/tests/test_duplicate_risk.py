import pytest
from fastapi.testclient import TestClient

from app.services.duplicate_risk import ApplicationMode, reject_autonomous_submission


def _ingest(client: TestClient, auth_headers: dict, **extra) -> dict:
    payload = {
        "source": "approved_remote_feeds",
        "external_id": extra.pop("external_id", "r21-test-1"),
        "title": extra.pop("title", "Director of Quality Engineering"),
        "company": extra.pop("company", "Example Health Tech"),
        "location": "Remote, US",
        "url": extra.pop("url", "https://example.com/jobs/director-qe"),
        "description_text": extra.pop("description_text", "Automation platform leadership"),
        "salary_min": 200000,
        "salary_max": 220000,
        **extra,
    }
    response = client.post("/api/jobs/ingest", headers=auth_headers, json=payload)
    assert response.status_code == 200
    return response.json()


def test_company_registry_and_duplicate_green(client: TestClient, auth_headers):
    job = _ingest(client, auth_headers, external_id="r21-green")
    risk = client.get(f"/api/companies/jobs/{job['id']}/duplicate-risk", headers=auth_headers)
    assert risk.status_code == 200
    body = risk.json()
    assert body["level"] == "GREEN"
    assert body["indicator"] == "No known conflict"

    companies = client.get("/api/companies", headers=auth_headers)
    assert companies.status_code == 200
    assert any(c["canonical_name"] == "Example Health Tech" for c in companies.json())


def test_exact_duplicate_url_blocked(client: TestClient, auth_headers):
    url = "https://example.com/jobs/exact-dup"
    first = _ingest(client, auth_headers, external_id="r21-dup-a", url=url)
    packet = client.post(f"/api/applications/jobs/{first['id']}/generate", headers=auth_headers)
    assert packet.status_code == 200
    approved = client.post(
        f"/api/applications/{packet.json()['id']}/actions",
        headers=auth_headers,
        json={"action": "mark_submitted"},
    )
    assert approved.status_code == 200

    second = _ingest(
        client,
        auth_headers,
        external_id="r21-dup-b",
        url=url,
        title="Senior Director of Quality Engineering",
    )
    risk = client.get(f"/api/companies/jobs/{second['id']}/duplicate-risk", headers=auth_headers)
    assert risk.status_code == 200
    assert risk.json()["level"] == "RED"
    assert "Exact duplicate" in risk.json()["indicator"]

    blocked = client.post(f"/api/applications/jobs/{second['id']}/generate", headers=auth_headers)
    assert blocked.status_code == 409


def test_duplicate_override(client: TestClient, auth_headers):
    url = "https://example.com/jobs/override-dup"
    first = _ingest(client, auth_headers, external_id="r21-ov-a", url=url)
    client.post(f"/api/applications/jobs/{first['id']}/generate", headers=auth_headers)
    second = _ingest(
        client,
        auth_headers,
        external_id="r21-ov-b",
        url=url,
        title="VP Quality Engineering",
    )
    risk = client.get(f"/api/companies/jobs/{second['id']}/duplicate-risk", headers=auth_headers)
    assert risk.json()["level"] == "RED"

    override = client.post(
        f"/api/companies/jobs/{second['id']}/duplicate-override",
        headers=auth_headers,
        json={"reason": "Distinct requisition confirmed by recruiter email thread."},
    )
    assert override.status_code == 200
    after = client.get(f"/api/companies/jobs/{second['id']}/duplicate-risk", headers=auth_headers)
    assert after.json()["level"] == "GREEN"
    assert "Override" in after.json()["indicator"]


def test_autonomous_mode_rejected(client: TestClient, auth_headers):
    response = client.post(
        "/api/companies/application-modes/validate",
        headers=auth_headers,
        json={"mode": ApplicationMode.AUTONOMOUS_LOCKED.value},
    )
    assert response.status_code == 200
    assert response.json()["allowed"] is False

    submit = client.post(
        "/api/applications/submit",
        headers=auth_headers,
        json={"mode": "AUTONOMOUS", "application_id": 1},
    )
    assert submit.status_code == 403

    with pytest.raises(ValueError):
        reject_autonomous_submission("AUTONOMOUS")


def test_application_modes_list(client: TestClient, auth_headers):
    response = client.get("/api/companies/application-modes", headers=auth_headers)
    assert response.status_code == 200
    modes = {m["id"]: m for m in response.json()["modes"]}
    assert modes["MANUAL"]["enabled"] is True
    assert modes["ASSISTED"]["enabled"] is True
    assert modes["AUTONOMOUS_LOCKED"]["enabled"] is False


def test_factual_core_in_packet_metadata(client: TestClient, auth_headers):
    job = _ingest(client, auth_headers, external_id="r21-factual")
    packet = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers)
    assert packet.status_code == 200
    meta = packet.json().get("packet_metadata") or {}
    assert meta.get("factual_core", {}).get("consistent") is True
    assert meta.get("factual_core", {}).get("hash")
    assert meta.get("duplicate_risk", {}).get("level") == "GREEN"


def test_ledger_recorded_on_packet(client: TestClient, auth_headers):
    job = _ingest(client, auth_headers, external_id="r21-ledger")
    client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers)
    ledger = client.get("/api/companies/ledger", headers=auth_headers)
    assert ledger.status_code == 200
    rows = ledger.json()
    assert any(row["job_id"] == job["id"] for row in rows)


def test_requisition_id_hard_block(client: TestClient, auth_headers):
    job_a = _ingest(
        client,
        auth_headers,
        external_id="r21-req-a",
        requisition_id="REQ-9001",
        url="https://example.com/jobs/req-a",
    )
    packet = client.post(f"/api/applications/jobs/{job_a['id']}/generate", headers=auth_headers)
    client.post(
        f"/api/applications/{packet.json()['id']}/actions",
        headers=auth_headers,
        json={"action": "mark_submitted"},
    )

    job_b = _ingest(
        client,
        auth_headers,
        external_id="r21-req-b",
        requisition_id="REQ-9001",
        url="https://example.com/jobs/req-b",
        title="Head of Quality Engineering",
    )
    risk = client.get(f"/api/companies/jobs/{job_b['id']}/duplicate-risk", headers=auth_headers)
    assert risk.json()["level"] == "RED"
