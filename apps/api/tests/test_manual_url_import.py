"""URL-only import and owner-confirmed manual opportunity (Workflow Lock 01)."""


def test_url_only_import_returns_needs_confirmation(client, auth_headers):
    response = client.post(
        "/api/workflows/import-url",
        headers=auth_headers,
        json={"url": "https://www.linkedin.com/jobs/view/9998887776"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "import_url"
    assert body["success"] == 0
    detail = (body.get("details") or [{}])[0]
    assert detail.get("status") == "NEEDS_CONFIRMATION"
    assert "NEEDS_CONFIRMATION" in (body.get("message") or "")


def test_duplicate_url_import_returns_existing_job(client, auth_headers):
    # Confirm with title+company first
    first = client.post(
        "/api/workflows/import-url",
        headers=auth_headers,
        json={
            "url": "https://example.com/jobs/manual-qe-1",
            "title": "Director, Quality Engineering",
            "company": "Acme Manual",
        },
    )
    assert first.status_code == 200
    job_id = (first.json().get("details") or [{}])[0].get("job_id")
    assert job_id

    second = client.post(
        "/api/workflows/import-url",
        headers=auth_headers,
        json={"url": "https://example.com/jobs/manual-qe-1"},
    )
    assert second.status_code == 200
    body = second.json()
    detail = (body.get("details") or [{}])[0]
    assert detail.get("status") == "DUPLICATE"
    assert detail.get("job_id") == job_id


def test_owner_confirmed_manual_opportunity_accessible(client, auth_headers):
    extract = client.post(
        "/api/opportunities/extract",
        headers=auth_headers,
        json={
            "url": "https://example.com/jobs/owner-qe-2",
            "title": "Senior Manager, Quality Engineering",
            "company": "Owner Corp",
            "plain_text": (
                "Senior Manager, Quality Engineering at Owner Corp\n"
                "Location: Remote, United States\n"
                "Lead the quality engineering organization."
            ),
        },
    )
    assert extract.status_code == 200
    extracted = extract.json()["extracted"]
    confirm = client.post(
        "/api/opportunities/confirm",
        headers=auth_headers,
        json={
            "extracted": {
                **extracted,
                "source": "manual_opportunity",
                "external_id": "owner-qe-2",
                "url": "https://example.com/jobs/owner-qe-2",
                "location": "Remote, United States",
                "owner_confirmed": True,
            },
            "resume_profile": "qe_manager",
        },
    )
    assert confirm.status_code == 200
    job_id = confirm.json()["job_id"]
    detail = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == job_id
