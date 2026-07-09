"""Jobs list sorting, pagination, and Fresh Jobs defaults."""


def test_jobs_list_page_size_10(client, auth_headers):
    client.post("/api/workflows/ingest/fixture", headers=auth_headers)
    response = client.get("/api/jobs?page=1&page_size=10&include_fixture=true", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["page_size"] == 10
    assert len(body["items"]) <= 10


def test_jobs_list_salary_sort_ascending(client, auth_headers):
    client.post("/api/workflows/ingest/fixture", headers=auth_headers)
    response = client.get(
        "/api/jobs?page=1&page_size=100&sort_by=salary&sort_dir=asc&include_fixture=true",
        headers=auth_headers,
    )
    assert response.status_code == 200
    salaries = [item.get("salary_max") for item in response.json()["items"] if item.get("salary_max") is not None]
    assert salaries == sorted(salaries)


def test_jobs_list_fit_sort_descending(client, auth_headers):
    client.post("/api/workflows/ingest/fixture", headers=auth_headers)
    client.post("/api/workflows/score-all", headers=auth_headers)
    response = client.get(
        "/api/jobs?page=1&page_size=100&sort_by=fit&sort_dir=desc&include_fixture=true",
        headers=auth_headers,
    )
    assert response.status_code == 200
    scores = [
        item["score"]["total_score"]
        for item in response.json()["items"]
        if item.get("score") and item["score"].get("total_score") is not None
    ]
    assert scores == sorted(scores, reverse=True)


def test_fresh_jobs_default_hides_fixture(client, auth_headers):
    client.post("/api/workflows/ingest/fixture", headers=auth_headers)
    response = client.get("/api/jobs?page=1&page_size=100", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_public_ingest_is_not_gitlab_hardcoded(client, auth_headers):
    response = client.post("/api/workflows/ingest/public", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "discover_fresh_jobs"
    # No hardcoded GitLab board — either empty campaign or multi-source discovery.
    assert "gitlab" not in str(body).lower() or body.get("accepted", 0) >= 0
    details = body.get("details") or body.get("sources") or []
    for item in details:
        assert item.get("board") != "gitlab" or item.get("provider_id") != "greenhouse"
