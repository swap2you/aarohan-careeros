from fastapi.testclient import TestClient


def test_matching_preferences(client: TestClient, auth_headers):
    response = client.get("/api/matching/preferences", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["target_base_salary_usd"] == 200000
    assert body["remote_first"] is True


def test_trust_and_fit_on_ingest(client: TestClient, auth_headers):
    response = client.post("/api/jobs/ingest/fixture", headers=auth_headers)
    assert response.status_code == 200
    job = response.json()[0]
    assert job["role_family"] is not None
    assert job["score"]["trust_score"] is not None
    assert job["score"]["hard_filter_passed"] is True
    assert job["score"]["fit_reasons"]
    assert job["score"]["match_card"]["headline"]


def test_match_card_endpoint(client: TestClient, auth_headers):
    job = client.post("/api/jobs/ingest/fixture", headers=auth_headers).json()[0]
    response = client.get(f"/api/matching/jobs/{job['id']}/card", headers=auth_headers)
    assert response.status_code == 200
    card = response.json()
    assert card["trust_score"] >= 0
    assert "role_family" in card


def test_hard_filter_rejects_low_salary(client: TestClient, auth_headers):
    from datetime import datetime

    payload = {
        "source": "approved_remote_feeds",
        "external_id": "trust-low-salary",
        "title": "Director of Quality Engineering",
        "company": "Low Pay Corp",
        "location": "Remote, United States",
        "url": "https://example.com/jobs/low-pay",
        "description_text": "Quality leadership role",
        "salary_min": 120000,
        "salary_max": 140000,
        "posted_at": datetime.utcnow().isoformat(),
    }
    job = client.post("/api/jobs/ingest", headers=auth_headers, json=payload).json()
    assert job.get("score") is not None
    # A failed trust hard-filter is an advisory ranking signal, not a lifecycle
    # transition: salary stays ranking/review and must not hard-reject the job's
    # lifecycle state (Workflow Lock 01 fit/lifecycle decoupling).
    assert job["score"]["hard_filter_passed"] is False
    assert job["score"]["recommendation"] == "REJECT"
    assert job["state"] != "REJECTED"


def test_hard_filter_rejects_relocation(client: TestClient, auth_headers):
    from datetime import datetime

    payload = {
        "source": "approved_remote_feeds",
        "external_id": "trust-reloc",
        "title": "Director of Quality Engineering",
        "company": "Relocate Co",
        "location": "Austin, TX - relocation required",
        "url": "https://example.com/jobs/reloc",
        "description_text": "Must relocate to Austin. No remote work. United States.",
        "salary_min": 200000,
        "salary_max": 230000,
        "posted_at": datetime.utcnow().isoformat(),
    }
    job = client.post("/api/jobs/ingest", headers=auth_headers, json=payload).json()
    assert job.get("score") is not None
    assert job["score"]["hard_filter_passed"] is False


def test_role_family_classification(client: TestClient, auth_headers):
    from app.services.trust_matching import classify_role_family

    assert classify_role_family("Director of Quality Engineering", "") == "qe_leadership"
    assert classify_role_family("Test Platform Architect", "automation platform") == "platform_architect"
    assert classify_role_family("Senior Technical Project Manager", "") == "tpm_delivery"
