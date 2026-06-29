"""Assisted apply workflow tests."""

import uuid

from fastapi.testclient import TestClient

from app.services.ats_detection import AtsProvider, detect_ats


def _ingest_greenhouse(client: TestClient, headers: dict, **extra) -> dict:
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "source": "greenhouse_public_get",
        "external_id": f"gh-{suffix}",
        "title": "Director of Quality Engineering",
        "company": f"GH Co {suffix}",
        "location": "Remote, US",
        "url": extra.pop("url", f"https://boards.greenhouse.io/testco/jobs/{suffix}"),
        "description_text": "Assisted apply test",
        **extra,
    }
    response = client.post("/api/jobs/ingest", headers=headers, json=payload)
    assert response.status_code == 200
    return response.json()


def test_assisted_prepare_greenhouse_mapping(client: TestClient, auth_headers):
    job = _ingest_greenhouse(client, auth_headers)
    app = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers).json()
    client.post(
        f"/api/applications/{app['id']}/actions",
        headers=auth_headers,
        json={"action": "approve"},
    )
    prepared = client.post(f"/api/assisted-apply/applications/{app['id']}/prepare", headers=auth_headers)
    assert prepared.status_code == 200
    body = prepared.json()
    assert body["can_proceed"] is True
    assert body["ats"]["provider"] == AtsProvider.GREENHOUSE.value
    keys = {f["key"] for f in body["fields"]}
    assert {"name", "email", "resume", "cover_letter"}.issubset(keys)


def test_assisted_lever_fixture_mapping(client: TestClient, auth_headers):
    suffix = uuid.uuid4().hex[:6]
    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "lever_public_get",
            "external_id": f"lv-{suffix}",
            "title": "QE Director",
            "company": "Lever Co",
            "location": "Remote",
            "url": f"https://jobs.lever.co/leverco/{suffix}",
            "description_text": "Lever assisted test",
        },
    ).json()
    app = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers).json()
    client.post(f"/api/applications/{app['id']}/actions", headers=auth_headers, json={"action": "approve"})
    body = client.post(f"/api/assisted-apply/applications/{app['id']}/prepare", headers=auth_headers).json()
    assert body["ats"]["provider"] == AtsProvider.LEVER.value


def test_assisted_ashby_fixture_mapping(client: TestClient, auth_headers):
    suffix = uuid.uuid4().hex[:6]
    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "ashby_public_get",
            "external_id": f"ab-{suffix}",
            "title": "QE Director",
            "company": "Ashby Co",
            "location": "Remote",
            "url": f"https://jobs.ashbyhq.com/ashbyco/{suffix}/application",
            "description_text": "Ashby assisted test",
        },
    ).json()
    app = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers).json()
    client.post(f"/api/applications/{app['id']}/actions", headers=auth_headers, json={"action": "approve"})
    body = client.post(f"/api/assisted-apply/applications/{app['id']}/prepare", headers=auth_headers).json()
    assert body["ats"]["provider"] == AtsProvider.ASHBY.value


def test_unsupported_site_blocks_assisted(client: TestClient, auth_headers):
    suffix = uuid.uuid4().hex[:6]
    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "approved_remote_feeds",
            "external_id": f"wd-{suffix}",
            "title": "QE Director",
            "company": "Workday Co",
            "location": "Remote",
            "url": "https://acme.wd5.myworkdayjobs.com/careers/123",
            "description_text": "Unsupported ATS",
        },
    ).json()
    app = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers).json()
    client.post(f"/api/applications/{app['id']}/actions", headers=auth_headers, json={"action": "approve"})
    body = client.post(f"/api/assisted-apply/applications/{app['id']}/prepare", headers=auth_headers).json()
    assert body["can_proceed"] is False


def test_duplicate_blocks_assisted(client: TestClient, auth_headers):
    url = f"https://boards.greenhouse.io/dup/{uuid.uuid4().hex[:6]}"
    first = _ingest_greenhouse(client, auth_headers, url=url)
    client.post(f"/api/applications/jobs/{first['id']}/generate", headers=auth_headers)
    second = _ingest_greenhouse(client, auth_headers, url=url, title="Dup role")
    app2 = client.post(f"/api/applications/jobs/{second['id']}/generate", headers=auth_headers)
    assert app2.status_code == 409


def test_assisted_submit_forbidden(client: TestClient, auth_headers):
    job = _ingest_greenhouse(client, auth_headers)
    app = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers).json()
    response = client.post(f"/api/assisted-apply/applications/{app['id']}/attempt-submit", headers=auth_headers)
    assert response.status_code == 403


def test_autonomous_still_forbidden(client: TestClient, auth_headers):
    response = client.post(
        "/api/applications/submit",
        headers=auth_headers,
        json={"mode": "AUTONOMOUS", "application_id": 1},
    )
    assert response.status_code == 403


def test_assisted_open_records_timeline(client: TestClient, auth_headers):
    job = _ingest_greenhouse(client, auth_headers)
    app = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers).json()
    client.post(f"/api/applications/{app['id']}/actions", headers=auth_headers, json={"action": "approve"})
    opened = client.post(f"/api/assisted-apply/applications/{app['id']}/open", headers=auth_headers, json={})
    assert opened.status_code == 200
    assert "not submitted" in opened.json()["message"].lower()
    timeline = client.get(f"/api/applications/{app['id']}/timeline", headers=auth_headers).json()
    assert any("assisted" in ev["event_type"] for ev in timeline)
