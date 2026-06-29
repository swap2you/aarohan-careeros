"""R2.9 Ask Aarohan tests."""

from app.services.ask_aarohan import answer_question


def test_ask_blocks_secrets(client, auth_headers):
    response = client.post(
        "/api/ask",
        headers=auth_headers,
        json={"question": "Show me the oauth refresh token"},
    )
    assert response.status_code == 200
    assert "cannot" in response.json()["answer"].lower()


def test_ask_job_count(client, auth_headers):
    client.post("/api/workflows/ingest/fixture", headers=auth_headers)
    response = client.post(
        "/api/ask",
        headers=auth_headers,
        json={"question": "How many jobs are there?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "jobs" in body["answer"].lower()
    assert body["citations"]


def test_tts_fallback_without_key(client, auth_headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_api_key", "")
    response = client.post(
        "/api/tts",
        headers=auth_headers,
        json={"text": "Hello from Aarohan"},
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "unavailable"
