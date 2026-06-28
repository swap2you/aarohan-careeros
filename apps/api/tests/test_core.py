from fastapi.testclient import TestClient

from app.main import app


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["scheduling_enabled"] is False


def test_setup_status(client: TestClient):
    response = client.get("/api/auth/setup-status")
    assert response.status_code == 200
    assert response.json()["has_admin"] is True


def test_source_policy_blocks_prohibited():
    from app.services.config_loader import source_policy

    policy = source_policy()
    assert "linkedin_scraping" in policy["prohibited"]
    assert "indeed_scraping" in policy["prohibited"]


def test_fixture_ingest_score_and_packet(client: TestClient, auth_headers):
    ingest = client.post("/api/jobs/ingest/fixture", headers=auth_headers)
    assert ingest.status_code == 200
    jobs = ingest.json()
    assert len(jobs) == 1
    assert jobs[0]["score"]["total_score"] >= 75

    job_id = jobs[0]["id"]
    packet = client.post(
        f"/api/applications/jobs/{job_id}/generate?resume_profile=qe_leadership",
        headers=auth_headers,
    )
    assert packet.status_code == 200
    assert packet.json()["state"] == "PACKET_READY"


def test_approval_boundary_no_external_submission(client: TestClient, auth_headers):
    job = client.post("/api/jobs/ingest/fixture", headers=auth_headers).json()[0]
    application = client.post(
        f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers
    ).json()

    approved = client.post(
        f"/api/applications/{application['id']}/actions",
        headers=auth_headers,
        json={"action": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["state"] == "APPROVED_FOR_SUBMISSION"

    routes = [route.path for route in app.routes]
    assert not any("submit-external" in path for path in routes)


def test_interview_pack_and_consulting(client: TestClient, auth_headers):
    job = client.post("/api/jobs/ingest/fixture", headers=auth_headers).json()[0]

    interview = client.post(f"/api/interviews/jobs/{job['id']}/generate", headers=auth_headers)
    assert interview.status_code == 200
    body = interview.json()
    assert "questions" in body
    assert "system_design" in body or body.get("questions", {}).get("system_design")

    lead = client.post(
        "/api/consulting/leads",
        headers=auth_headers,
        json={
            "company": "Acme Corp",
            "problem_summary": "Need flaky test reduction in CI/CD pipelines",
        },
    )
    assert lead.status_code == 200
    assert "Flaky Test Reduction Program" in lead.json()["recommended_service"]


def test_ai_budget_cap(client: TestClient, auth_headers):
    budget = client.get("/api/ai/budget", headers=auth_headers)
    assert budget.status_code == 200
    assert budget.json()["hard_cap_active"] is True


def test_deduplication(client: TestClient, auth_headers):
    payload = {
        "source": "approved_remote_feeds",
        "external_id": "dup-1",
        "title": "Director of Quality Engineering",
        "company": "Example Health Tech",
        "location": "Remote, US",
        "url": "https://example.com/jobs/director-qe",
        "description_text": "Automation platform leadership",
        "salary_min": 200000,
        "salary_max": 220000,
    }
    first = client.post("/api/jobs/ingest", headers=auth_headers, json=payload)
    second = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={**payload, "external_id": "dup-2"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_workflow_ingest_fixture(client: TestClient, auth_headers):
    response = client.post("/api/workflows/ingest/fixture", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["success"] >= 1


def test_gmail_fixture_sync(client: TestClient, auth_headers):
    response = client.post("/api/integrations/gmail/sync-fixture", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["processed"] >= 1


def test_integration_status(client: TestClient, auth_headers):
    response = client.get("/api/integrations/status", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["fixture_mode"] is True


def test_resume_profiles(client: TestClient, auth_headers):
    from app.services.resume_builder import load_resume_profile

    for profile in ["qe_leadership", "platform_architect", "ai_enabled_qe"]:
        data = load_resume_profile(profile)
        assert data["id"] == profile

    workflow = client.post("/api/workflows/ingest/fixture", headers=auth_headers).json()
    job_id = workflow["details"][0]["job_id"]
    response = client.post(
        f"/api/applications/jobs/{job_id}/generate?resume_profile=platform_architect",
        headers=auth_headers,
    )
    assert response.status_code == 200


def test_sanitize_html_strips_script():
    from app.services.sanitize import sanitize_html

    cleaned = sanitize_html("<script>alert('x')</script><p>Hello</p>")
    assert "script" not in cleaned.lower()
    assert "Hello" in cleaned
