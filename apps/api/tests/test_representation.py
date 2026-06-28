"""Vendor/client representation conflict tests."""

import uuid

from fastapi.testclient import TestClient

from app.services.duplicate_risk import normalize_company_name


def test_representation_api_and_job_risk(client: TestClient, auth_headers):
    suffix = uuid.uuid4().hex[:6]
    client_name = f"Client Corp {suffix}"
    req = f"REQ-{suffix}"
    created = client.post(
        "/api/representations",
        headers=auth_headers,
        json={
            "vendor_name": "Test Staffing LLC",
            "client_name": client_name,
            "requisition_id": req,
            "role_title": "Director QE",
            "status": "active",
        },
    )
    assert created.status_code == 200

    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "approved_remote_feeds",
            "external_id": f"rep-job-{suffix}",
            "title": "Director QE",
            "company": client_name,
            "location": "Remote, US",
            "url": f"https://example.com/rep/{suffix}",
            "description_text": "Vendor conflict test",
            "requisition_id": req,
        },
    ).json()

    risk = client.get(f"/api/representations/jobs/{job['id']}/representation-risk", headers=auth_headers)
    assert risk.status_code == 200
    assert risk.json()["level"] == "RED"


def test_expired_representation_amber(client: TestClient, auth_headers):
    from datetime import datetime, timedelta

    suffix = uuid.uuid4().hex[:6]
    client_name = f"Expired Client {suffix}"
    client.post(
        "/api/representations",
        headers=auth_headers,
        json={
            "vendor_name": "Old Vendor",
            "client_name": client_name,
            "status": "expired",
            "representation_end": (datetime.utcnow() - timedelta(days=10)).isoformat(),
        },
    )
    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "approved_remote_feeds",
            "external_id": f"exp-{suffix}",
            "title": "Director QE",
            "company": client_name,
            "location": "Remote, US",
            "url": f"https://example.com/exp/{suffix}",
            "description_text": "Expired representation test",
        },
    ).json()
    risk = client.get(f"/api/representations/jobs/{job['id']}/representation-risk", headers=auth_headers)
    assert risk.status_code == 200
    assert risk.json()["level"] == "AMBER"


def test_representation_override(client: TestClient, auth_headers):
    suffix = uuid.uuid4().hex[:6]
    client_name = f"Override Client {suffix}"
    client.post(
        "/api/representations",
        headers=auth_headers,
        json={
            "vendor_name": "Block Vendor",
            "client_name": client_name,
            "requisition_id": f"REQ-OV-{suffix}",
            "status": "active",
        },
    )
    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "approved_remote_feeds",
            "external_id": f"ov-{suffix}",
            "title": "Director QE",
            "company": client_name,
            "location": "Remote, US",
            "url": f"https://example.com/ov/{suffix}",
            "description_text": "Override test",
            "requisition_id": f"REQ-OV-{suffix}",
        },
    ).json()
    override = client.post(
        f"/api/representations/jobs/{job['id']}/representation-override",
        headers=auth_headers,
        json={"reason": "Confirmed no signed representation agreement applies."},
    )
    assert override.status_code == 200
    risk = client.get(f"/api/representations/jobs/{job['id']}/representation-risk", headers=auth_headers)
    assert risk.json()["level"] == "GREEN"
