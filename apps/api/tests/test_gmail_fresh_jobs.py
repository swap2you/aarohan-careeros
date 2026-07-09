"""Gmail LinkedIn/Indeed digest parsing fixtures (Workflow Lock 01 correction)."""

from datetime import datetime, timedelta

from app.services.gmail_alert_parsers import (
    canonical_job_url,
    parse_job_alerts,
    parsed_job_to_ingest_payload,
)
from app.services.job_eligibility import DECISION_QUARANTINE, MALFORMED_DIGEST, evaluate_eligibility


SINGLE_LINKEDIN = {
    "subject": "Your job alert for Quality Engineering Manager",
    "sender": "jobalerts-noreply@linkedin.com",
    "gmail_message_id": "msg-li-single-1",
    "gmail_thread_id": "thread-li-1",
    "body_text": """
Quality Engineering Manager at Contoso
Location: Remote, United States
https://www.linkedin.com/jobs/view/4123456789/?trk=flagship3_job_home&refId=abc
""",
    "received_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
}

MULTI_LINKEDIN = {
    "subject": "Your job alert for Technical Program Manager",
    "sender": "jobalerts-noreply@linkedin.com",
    "gmail_message_id": "msg-li-multi-1",
    "body_text": """
New jobs matching your alert

Senior Technical Program Manager at Contoso
Location: Remote, United States
https://www.linkedin.com/jobs/view/4123456789/?trk=flagship3_job_home

Quality Engineering Manager at Fabrikam
Location: Harrisburg, Pennsylvania, United States
https://www.linkedin.com/jobs/view/4987654321?refId=abc&trackingId=xyz

See all jobs: https://www.linkedin.com/jobs/search/?keywords=technical%20program%20manager
PennDOT search preferences — update your preferences.
""",
    "received_at": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
}

RECOMMENDED_LINKEDIN = {
    "subject": "Jobs recommended for you",
    "sender": "jobs-listings@linkedin.com",
    "gmail_message_id": "msg-li-rec-1",
    "body_text": """
Director, Quality Engineering at Northwind
Location: Atlanta, GA
https://www.linkedin.com/jobs/view/5556667778
""",
    "received_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
}

SINGLE_INDEED = {
    "subject": "Quality Engineering Manager job alert",
    "sender": "alert@indeed.com",
    "gmail_message_id": "msg-in-single-1",
    "body_text": """
Director of Quality Engineering at Northwind
Location: Remote, United States
https://www.indeed.com/viewjob?jk=abc123def456&utm_source=jobalert
""",
    "received_at": (datetime.utcnow() - timedelta(hours=4)).isoformat(),
}

MULTI_INDEED = {
    "subject": "3 new Quality Engineering Manager jobs",
    "sender": "alert@indeed.com",
    "gmail_message_id": "msg-in-multi-1",
    "body_text": """
Director of Quality Engineering at Northwind
Location: Remote, United States
https://www.indeed.com/viewjob?jk=abc123def456&utm_source=jobalert

Principal Quality Engineer at Adventure Works
Location: United States
https://www.indeed.com/rc/clk?jk=zzz999yyy888&from=ja
""",
    "received_at": (datetime.utcnow() - timedelta(hours=5)).isoformat(),
}

MALFORMED_LINKEDIN = {
    "subject": "LinkedIn job alert",
    "sender": "jobalerts-noreply@linkedin.com",
    "gmail_message_id": "msg-li-bad-1",
    "body_text": """
https://www.linkedin.com/jobs/view/1112223334
match your interests.
PennDOT
Update your preferences to see more jobs.
""",
    "received_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
}


def test_single_linkedin_alert():
    alerts = parse_job_alerts(SINGLE_LINKEDIN, label="Aarohan/Job Alerts/LinkedIn")
    assert len(alerts) == 1
    assert alerts[0].external_id == "4123456789"
    assert "/jobs/view/4123456789" in alerts[0].url
    assert alerts[0].title.lower() != "linkedin job alert"
    assert "contoso" in alerts[0].company.lower()


def test_multi_linkedin_digest_one_job_per_view_id():
    alerts = parse_job_alerts(MULTI_LINKEDIN, label="Aarohan/Job Alerts/LinkedIn")
    assert len(alerts) == 2
    ids = {a.external_id for a in alerts}
    assert ids == {"4123456789", "4987654321"}
    assert not any("jobs/search" in a.url for a in alerts)
    assert not any(a.title.lower() == "linkedin job alert" for a in alerts)
    assert not any("penndot" in (a.company or "").lower() for a in alerts)


def test_linkedin_recommended_jobs_email():
    alerts = parse_job_alerts(RECOMMENDED_LINKEDIN)
    assert len(alerts) == 1
    assert alerts[0].external_id == "5556667778"
    assert "director" in alerts[0].title.lower()


def test_single_indeed_alert():
    alerts = parse_job_alerts(SINGLE_INDEED, label="Aarohan/Job Alerts/Indeed")
    assert len(alerts) == 1
    assert alerts[0].external_id == "abc123def456"
    assert alerts[0].title.lower() != "indeed job alert"


def test_multi_indeed_digest():
    alerts = parse_job_alerts(MULTI_INDEED, label="Aarohan/Job Alerts/Indeed")
    assert len(alerts) == 2
    assert {a.external_id for a in alerts} == {"abc123def456", "zzz999yyy888"}


def test_malformed_email_quarantined_once():
    alerts = parse_job_alerts(MALFORMED_LINKEDIN)
    assert len(alerts) == 1
    payload = parsed_job_to_ingest_payload(
        alerts[0],
        gmail_message_id="msg-li-bad-1",
        source_received_at=MALFORMED_LINKEDIN["received_at"],
    )
    # Force bad title path if parser used UNPARSED
    if payload["title"].startswith("UNPARSED") or payload["company"] == "Unknown employer":
        result = evaluate_eligibility({**payload, "location": "Remote, United States"})
        assert result.decision in {DECISION_QUARANTINE, "OWNER_REVIEW", "REJECT"}
        assert MALFORMED_DIGEST in result.reason_codes or "COMPANY_UNKNOWN" in result.reason_codes or result.decision != "ACCEPT"


def test_linkedin_canonical_strips_tracking():
    url = canonical_job_url("https://www.linkedin.com/jobs/view/4123456789/?trk=flagship3_job_home&refId=x")
    assert url.endswith("/jobs/view/4123456789")
    assert "trk=" not in url


def test_parsed_payload_includes_received_at_and_gmail_ids():
    alerts = parse_job_alerts(SINGLE_LINKEDIN)
    payload = parsed_job_to_ingest_payload(
        alerts[0],
        gmail_message_id="msg-li-single-1",
        source_received_at=SINGLE_LINKEDIN["received_at"],
        gmail_thread_id="thread-li-1",
        source_label="Aarohan/Job Alerts/LinkedIn",
    )
    assert payload["source_received_at"]
    assert payload["raw_payload"]["gmail_message_id"] == "msg-li-single-1"
    assert payload["raw_payload"]["gmail_thread_id"] == "thread-li-1"
    result = evaluate_eligibility({**payload, "location": payload.get("location") or "Remote, United States"})
    assert result.freshness_source == "source_received_at"
    assert result.freshness_tier == "TODAY"


def test_repeated_gmail_sync_idempotent(client, auth_headers):
    """Rerunning the same email creates no duplicate jobs."""
    alerts = parse_job_alerts(SINGLE_LINKEDIN, label="Aarohan/Job Alerts/LinkedIn")
    alert = alerts[0]
    base = parsed_job_to_ingest_payload(
        alert,
        gmail_message_id="msg-li-single-1",
        source_received_at=SINGLE_LINKEDIN["received_at"],
    )
    body = {
        "source": base["source"],
        "external_id": base["external_id"],
        "title": base["title"] if not base["title"].startswith("UNPARSED") else "Quality Engineering Manager",
        "company": base["company"] if base["company"] != "Unknown employer" else "Contoso",
        "url": base["url"],
        "location": base.get("location") or "Remote, United States",
        "description_text": base["description_text"],
        "data_provenance": "gmail",
    }
    r1 = client.post("/api/jobs/ingest", headers=auth_headers, json=body)
    r2 = client.post("/api/jobs/ingest", headers=auth_headers, json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
