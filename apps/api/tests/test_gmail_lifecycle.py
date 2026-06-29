"""R2.7 Gmail lifecycle tests."""

from __future__ import annotations

from app.integrations.google import FixtureGmailClient
from app.services.gmail_alert_parsers import parse_job_alert
from app.services.gmail_lifecycle import (
    INTERVIEW,
    JOB_ALERT,
    OFFER,
    REJECTION,
    classify_message,
    correct_classification,
    sync_messages,
)


def test_parse_linkedin_alert_fixture():
    msg = {
        "sender": "jobs-noreply@linkedin.com",
        "subject": "New jobs: Director of QE",
        "body_text": "Director at Acme https://www.linkedin.com/jobs/view/12345 Location: Remote",
    }
    alert = parse_job_alert(msg, label="Aarohan/Job Alerts/LinkedIn")
    assert alert is not None
    assert alert.source == "linkedin_alert_emails"
    assert "Acme" in alert.company


def test_parse_indeed_alert_fixture():
    msg = {
        "sender": "alert@indeed.com",
        "subject": "Indeed Alert",
        "body_text": "Company: Beta\nhttps://www.indeed.com/viewjob?jk=abc123",
    }
    alert = parse_job_alert(msg, label="Aarohan/Job Alerts/Indeed")
    assert alert is not None
    assert alert.external_id == "abc123"


def test_classify_lifecycle_types():
    assert classify_message({"subject": "Offer", "body_text": "pleased to extend an offer"})[0] == OFFER
    assert classify_message({"subject": "Update", "body_text": "not moving forward"})[0] == REJECTION
    assert classify_message({"subject": "Interview", "body_text": "schedule a call"})[0] == INTERVIEW


def test_fixture_sync_ingests_jobs_and_idempotent(client, auth_headers):
    first = client.post("/api/integrations/gmail/sync-fixture", headers=auth_headers)
    assert first.status_code == 200
    body = first.json()
    assert body["processed"] >= 5
    assert body["jobs_ingested"] >= 4

    second = client.post("/api/integrations/gmail/sync-fixture", headers=auth_headers)
    assert second.status_code == 200
    replay = second.json()
    assert replay["skipped"] >= body["processed"]


def test_duplicate_message_not_reprocessed(client, auth_headers):
    client.post("/api/integrations/gmail/sync-fixture", headers=auth_headers)
    signals = client.get("/api/recruiter-signals", headers=auth_headers).json()
    assert any(s.get("gmail_label") for s in signals)
    assert all("body_text" not in s for s in signals)


def test_user_classification_correction(client, auth_headers):
    client.post("/api/integrations/gmail/sync-fixture", headers=auth_headers)
    signals = client.get("/api/recruiter-signals", headers=auth_headers).json()
    target = next(s for s in signals if s["original_classification"] == JOB_ALERT)
    patched = client.patch(
        f"/api/recruiter-signals/{target['id']}/classification",
        headers=auth_headers,
        params={"classification": "UNRELATED"},
    )
    assert patched.status_code == 200
    assert patched.json()["signal_type"] == "UNRELATED"


def test_fixture_client_loads_corpus():
    messages = FixtureGmailClient().fetch_recent_messages(max_results=20)
    assert len(messages) >= 9
    labels = {m.get("label") for m in messages}
    assert "Aarohan/Job Alerts/LinkedIn" in labels
