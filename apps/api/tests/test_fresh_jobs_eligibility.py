"""Workflow Lock 01 — Fresh Jobs eligibility, freshness, geography, and role gates."""

from datetime import datetime, timedelta

from app.services.job_eligibility import (
    AMBIGUOUS,
    DECISION_ACCEPT,
    DECISION_QUARANTINE,
    DECISION_REJECT,
    DECISION_SECONDARY,
    ELIGIBLE_LOCAL,
    ELIGIBLE_US,
    FOREIGN_ONLY,
    INELIGIBLE_FOREIGN,
    REMOTE_ELIGIBILITY_AMBIGUOUS,
    ROLE_OUT_OF_SCOPE,
    SAVED_SEARCH_URL_NOT_JOB_URL,
    STALE_OVER_48_HOURS,
    TIMESTAMP_UNKNOWN,
    evaluate_eligibility,
    evaluate_location,
    is_saved_search_url,
)


def _base(**overrides):
    payload = {
        "source": "remotive_public_get",
        "external_id": "1",
        "title": "Technical Program Manager",
        "company": "Acme Corp",
        "location": "Remote — United States",
        "url": "https://example.com/jobs/tpm-1",
        "description_text": "Lead technical programs across quality platforms.",
        "posted_at": datetime.utcnow().isoformat(),
    }
    payload.update(overrides)
    return payload


def test_us_remote_accepted():
    result = evaluate_eligibility(_base())
    assert result.decision == DECISION_ACCEPT
    assert result.location_eligibility == ELIGIBLE_US


def test_pennsylvania_hybrid_accepted():
    result = evaluate_eligibility(
        _base(
            title="Quality Engineering Manager",
            location="Harrisburg, PA",
            workplace_type="hybrid",
            description_text="Hybrid role in Harrisburg / Central Pennsylvania.",
        )
    )
    assert result.decision == DECISION_ACCEPT
    assert result.location_eligibility in {ELIGIBLE_LOCAL, ELIGIBLE_US}


def test_canada_only_remote_rejected():
    result = evaluate_eligibility(
        _base(location="Remote, Canada", description_text="Remote Canada only. Must work in Canada.")
    )
    assert result.decision == DECISION_REJECT
    assert FOREIGN_ONLY in result.reason_codes
    assert result.location_eligibility == INELIGIBLE_FOREIGN


def test_bangalore_only_rejected():
    result = evaluate_eligibility(_base(location="Bangalore, India", description_text="Onsite Bangalore"))
    assert result.decision == DECISION_REJECT
    assert FOREIGN_ONLY in result.reason_codes


def test_france_only_rejected():
    result = evaluate_eligibility(_base(location="Paris, France", description_text="Europe only"))
    assert result.decision == DECISION_REJECT


def test_unspecified_remote_quarantined():
    result = evaluate_eligibility(
        _base(location="Remote", description_text="Fully remote role. Work from anywhere.")
    )
    assert result.decision == DECISION_QUARANTINE
    assert REMOTE_ELIGIBILITY_AMBIGUOUS in result.reason_codes
    assert result.location_eligibility == AMBIGUOUS


def test_24h_job_accepted():
    posted = datetime.utcnow() - timedelta(hours=12)
    result = evaluate_eligibility(_base(posted_at=posted.isoformat()))
    assert result.decision == DECISION_ACCEPT
    assert result.freshness_bucket == "NEW"


def test_48h_boundary_accepted():
    posted = datetime.utcnow() - timedelta(hours=47, minutes=30)
    result = evaluate_eligibility(_base(posted_at=posted.isoformat()))
    assert result.decision == DECISION_ACCEPT
    assert result.freshness_bucket == "RECENT"


def test_older_than_48h_rejected():
    posted = datetime.utcnow() - timedelta(hours=60)
    result = evaluate_eligibility(_base(posted_at=posted.isoformat()))
    assert result.decision == DECISION_REJECT
    assert STALE_OVER_48_HOURS in result.reason_codes


def test_missing_automated_timestamp_quarantined():
    payload = _base()
    payload.pop("posted_at")
    result = evaluate_eligibility(payload)
    assert result.decision == DECISION_QUARANTINE
    assert TIMESTAMP_UNKNOWN in result.reason_codes


def test_gmail_received_at_becomes_effective_freshness():
    received = datetime.utcnow() - timedelta(hours=6)
    payload = _base()
    payload.pop("posted_at")
    payload["source"] = "linkedin_alert_emails"
    payload["source_received_at"] = received.isoformat()
    result = evaluate_eligibility(payload)
    assert result.decision == DECISION_ACCEPT
    assert result.freshness_source == "source_received_at"
    assert result.effective_freshness_at is not None


def test_linkedin_saved_search_url_rejected():
    assert is_saved_search_url("https://www.linkedin.com/jobs/search/?keywords=tpm")
    result = evaluate_eligibility(
        _base(url="https://www.linkedin.com/jobs/search/?keywords=tpm&location=United%20States")
    )
    assert result.decision == DECISION_REJECT
    assert SAVED_SEARCH_URL_NOT_JOB_URL in result.reason_codes


def test_target_tpm_accepted():
    result = evaluate_eligibility(_base(title="Senior Technical Program Manager"))
    assert result.decision == DECISION_ACCEPT
    assert result.recommended_profile == "tpm_delivery"


def test_target_qe_manager_accepted():
    result = evaluate_eligibility(_base(title="Senior Manager, Quality Engineering"))
    assert result.decision == DECISION_ACCEPT
    assert result.recommended_profile == "qe_manager"


def test_director_qe_accepted():
    result = evaluate_eligibility(_base(title="Director of Quality Engineering"))
    assert result.decision == DECISION_ACCEPT
    assert result.recommended_profile == "director_qe"


def test_principal_architect_accepted():
    result = evaluate_eligibility(_base(title="Quality Engineering Architect"))
    assert result.decision == DECISION_ACCEPT
    assert result.recommended_profile == "platform_architect"


def test_generic_backend_engineer_rejected():
    result = evaluate_eligibility(_base(title="Senior Backend Engineer"))
    assert result.decision == DECISION_REJECT
    assert ROLE_OUT_OF_SCOPE in result.reason_codes


def test_generic_product_manager_rejected():
    result = evaluate_eligibility(_base(title="Product Manager"))
    assert result.decision == DECISION_REJECT
    assert ROLE_OUT_OF_SCOPE in result.reason_codes


def test_profile_scores_generated():
    result = evaluate_eligibility(_base(title="Technical Program Manager"))
    assert result.profile_scores
    assert result.profile_scores.get("tpm_delivery", 0) > 0


def test_foreign_remote_ok_style_rejected():
    loc, _ = evaluate_location(
        {
            "title": "Remote Software Engineer",
            "location": "Remote (India)",
            "description_text": "Work from India. Bangalore preferred.",
        }
    )
    assert loc == INELIGIBLE_FOREIGN
