"""LinkedIn/Indeed digest parsing tests."""

from app.services.gmail_alert_parsers import canonical_job_url, parse_job_alerts


def test_linkedin_digest_splits_multiple_jobs():
    message = {
        "subject": "New jobs for you",
        "body_text": """
        Senior TPM at Acme Corp
        https://www.linkedin.com/jobs/view/111?trackingId=abc&refId=xyz

        QE Manager at Beta Systems
        https://www.linkedin.com/jobs/view/222?trackingId=def
        """,
    }
    alerts = parse_job_alerts(message, label="Aarohan/Job Alerts/LinkedIn")
    assert len(alerts) == 2
    assert alerts[0].external_id == "111"
    assert alerts[1].external_id == "222"
    assert "Acme" in alerts[0].company or "TPM" in alerts[0].title
    assert alerts[0].description_text != message["body_text"]


def test_canonical_linkedin_url_strips_tracking():
    raw = "https://www.linkedin.com/jobs/view/12345?trackingId=abc&refId=xyz"
    clean = canonical_job_url(raw)
    assert "trackingId" not in clean
    assert clean.endswith("/12345")


def test_indeed_digest_splits_entries():
    message = {
        "subject": "Indeed alert",
        "body_text": """
        Director QE at Gamma LLC
        https://www.indeed.com/viewjob?jk=abc123&utm_source=email

        Architect at Delta
        https://www.indeed.com/viewjob?jk=def456&utm_campaign=alert
        """,
    }
    alerts = parse_job_alerts(message, label="Aarohan/Job Alerts/Indeed")
    assert len(alerts) == 2
    assert {a.external_id for a in alerts} == {"abc123", "def456"}
