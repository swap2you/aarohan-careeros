"""Workflow Lock 01 correction — eligibility, freshness tiers, geography, roles, salary."""

from datetime import datetime, timedelta

from app.services.job_eligibility import (
    AMBIGUOUS,
    COMPENSATION_REVIEW,
    DECISION_ACCEPT,
    DECISION_HISTORICAL,
    DECISION_OWNER_REVIEW,
    DECISION_QUARANTINE,
    DECISION_REJECT,
    ELIGIBLE_LOCAL,
    ELIGIBLE_US,
    FOREIGN_ONLY,
    INELIGIBLE_FOREIGN,
    REMOTE_ELIGIBILITY_AMBIGUOUS,
    ROLE_OUT_OF_SCOPE,
    SALARY_REVIEW,
    SAVED_SEARCH_URL_NOT_JOB_URL,
    STALE_HISTORICAL,
    TIMESTAMP_UNKNOWN,
    TIER_FRESH,
    TIER_HISTORICAL,
    TIER_RECENT,
    TIER_TODAY,
    evaluate_eligibility,
    evaluate_location,
    is_saved_search_url,
)
from app.services.title_normalization import normalize_title, pattern_in_title


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


# --- 1. GitLab false positives must fail owner eligibility ---
GITLAB_FALSE_POSITIVES = [
    "Commercial Account Executive - Nordics",
    "Customer Success Engineer, India",
    "Customer Success Manager - Australia",
    "New Business Account Executive - Nordics",
    "Renewals Manager - Australia",
    "Senior Professional Services Engineer - Japan",
    "People Business Partner Leader",
    "Backend Engineer",
]


def test_gitlab_false_positives_rejected():
    for title in GITLAB_FALSE_POSITIVES:
        result = evaluate_eligibility(
            _base(
                title=title,
                company="GitLab",
                source="greenhouse_public_get",
                location="Remote",
                description_text="Join GitLab. Quality engineering culture. Program managers welcome.",
            )
        )
        assert result.decision == DECISION_REJECT, f"{title} -> {result.decision} {result.reason_codes}"
        assert result.owner_visible is False
        assert ROLE_OUT_OF_SCOPE in result.reason_codes or FOREIGN_ONLY in result.reason_codes


def test_gitlab_foreign_roles_rejected_by_geography():
    for title, loc in [
        ("Customer Success Engineer, India", "India"),
        ("Customer Success Manager - Australia", "Australia"),
        ("Senior Professional Services Engineer - Japan", "Japan"),
        ("Commercial Account Executive - Nordics", "Nordics / EMEA"),
    ]:
        result = evaluate_eligibility(_base(title=title, location=loc, company="GitLab"))
        assert result.decision == DECISION_REJECT
        assert result.owner_visible is False


# --- 2 & 3. Target titles + punctuation ---
TARGET_TITLES = [
    ("Director, Quality Engineering", "director_qe"),
    ("Director Quality Engineering - Digital Products", "director_qe"),
    ("Director, Quality Engineering & Platform Reliability", "director_qe"),
    ("Senior Manager, Quality Engineering", "qe_manager"),
    ("Manager, Quality Engineering (Automation)", "qe_manager"),
    ("QA Engineering Manager", "qe_manager"),
    ("Head of Observability & Quality Engineering", "director_qe"),
    ("Head of Quality Assurance and Technical Enablement", "director_qe"),
    ("Principal Quality Engineer", "platform_architect"),
    ("Remote Senior Manager, ACAS Quality Engineering", "qe_manager"),
]


def test_target_titles_match_profiles():
    for title, profile in TARGET_TITLES:
        result = evaluate_eligibility(_base(title=title))
        assert result.decision == DECISION_ACCEPT, f"{title} -> {result.decision} {result.reasons}"
        assert result.recommended_profile == profile, f"{title} -> {result.recommended_profile}"
        assert result.normalized_title


def test_punctuation_does_not_break_role_matching():
    assert pattern_in_title("director quality engineering", "Director, Quality Engineering")
    assert pattern_in_title(
        "director quality engineering",
        "Director, Quality Engineering & Platform Reliability",
    )
    assert pattern_in_title("manager quality engineering", "Manager, Quality Engineering (Automation)")
    assert normalize_title("Head of Observability & Quality Engineering") == (
        "head of observability and quality engineering"
    )


# --- 4 & 5. Geography ---
def test_atlanta_and_northford_classify_as_us():
    for loc in ["Atlanta, Fulton County, GA", "Atlanta, GA", "Northford, New Haven County, CT", "Northford, CT"]:
        loc_elig, reason, country, state, _ = evaluate_location({"title": "QE Manager", "location": loc})
        assert loc_elig == ELIGIBLE_US, f"{loc} -> {loc_elig} {reason}"
        assert country == "US"
        result = evaluate_eligibility(_base(title="Quality Engineering Manager", location=loc))
        assert result.decision == DECISION_ACCEPT
        assert FOREIGN_ONLY not in result.reason_codes


def test_foreign_india_japan_australia_nordics_emea_rejected():
    for loc in ["Bangalore, India", "Tokyo, Japan", "Sydney, Australia", "Stockholm, Nordics", "EMEA Remote"]:
        result = evaluate_eligibility(
            _base(title="Quality Engineering Manager", location=loc, description_text=f"Role based in {loc}")
        )
        assert result.decision == DECISION_REJECT
        assert FOREIGN_ONLY in result.reason_codes


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


def test_unspecified_remote_owner_review():
    result = evaluate_eligibility(
        _base(location="Remote", description_text="Fully remote role. Work from anywhere.")
    )
    assert result.decision == DECISION_OWNER_REVIEW
    assert REMOTE_ELIGIBILITY_AMBIGUOUS in result.reason_codes
    assert result.location_eligibility == AMBIGUOUS


# --- 7–12. Freshness tiers ---
def test_gmail_received_at_becomes_effective_freshness():
    received = datetime.utcnow() - timedelta(hours=6)
    payload = _base()
    payload.pop("posted_at")
    payload["source"] = "linkedin_alert_emails"
    payload["source_received_at"] = received.isoformat()
    result = evaluate_eligibility(payload)
    assert result.decision == DECISION_ACCEPT
    assert result.freshness_source == "source_received_at"
    assert result.freshness_tier == TIER_TODAY


def test_today_tier_0_24h():
    posted = datetime.utcnow() - timedelta(hours=12)
    result = evaluate_eligibility(_base(posted_at=posted.isoformat()))
    assert result.decision == DECISION_ACCEPT
    assert result.freshness_tier == TIER_TODAY
    assert result.owner_visible is True


def test_fresh_tier_25_72h():
    posted = datetime.utcnow() - timedelta(hours=36)
    result = evaluate_eligibility(_base(posted_at=posted.isoformat()))
    assert result.decision == DECISION_ACCEPT
    assert result.freshness_tier == TIER_FRESH
    assert result.owner_visible is True


def test_recent_tier_3_7_days():
    posted = datetime.utcnow() - timedelta(days=4)
    result = evaluate_eligibility(_base(posted_at=posted.isoformat()))
    assert result.decision == DECISION_ACCEPT
    assert result.freshness_tier == TIER_RECENT
    assert result.owner_visible is True


def test_historical_over_seven_days():
    posted = datetime.utcnow() - timedelta(days=8)
    result = evaluate_eligibility(_base(posted_at=posted.isoformat()))
    assert result.decision == DECISION_HISTORICAL
    assert result.freshness_tier == TIER_HISTORICAL
    assert STALE_HISTORICAL in result.reason_codes
    assert result.owner_visible is False


def test_shortlisted_never_hidden_by_age():
    posted = datetime.utcnow() - timedelta(days=30)
    result = evaluate_eligibility(
        _base(posted_at=posted.isoformat(), state="SHORTLISTED", title="Director, Quality Engineering")
    )
    assert result.freshness_tier == TIER_HISTORICAL
    assert result.decision == DECISION_ACCEPT
    assert result.owner_visible is True
    assert STALE_HISTORICAL not in result.reason_codes


def test_packet_ready_never_hidden_by_age():
    posted = datetime.utcnow() - timedelta(days=20)
    result = evaluate_eligibility(
        _base(posted_at=posted.isoformat(), state="PACKET_READY", title="QA Engineering Manager")
    )
    assert result.decision == DECISION_ACCEPT
    assert result.owner_visible is True
    assert STALE_HISTORICAL not in result.reason_codes


def test_timestamp_unknown_strong_role_owner_review():
    payload = _base(title="Senior Director, Quality Engineering & Observability")
    payload.pop("posted_at")
    result = evaluate_eligibility(payload)
    assert result.decision == DECISION_OWNER_REVIEW
    assert TIMESTAMP_UNKNOWN in result.reason_codes
    assert result.recommended_profile == "director_qe"


# --- 13. Salary ---
def test_salary_below_170k_is_review_not_reject():
    result = evaluate_eligibility(
        _base(title="Director, Quality Engineering", salary_max=150000, salary_min=140000)
    )
    assert result.decision == DECISION_ACCEPT
    assert result.salary_tier == SALARY_REVIEW
    assert COMPENSATION_REVIEW in result.reason_codes
    assert result.owner_visible is True


# --- 14. Audit/live identical ---
def test_audit_and_live_identical_decisions():
    payload = _base(title="Director, Quality Engineering", location="Atlanta, GA")
    a = evaluate_eligibility(payload)
    b = evaluate_eligibility(dict(payload))
    assert a.decision == b.decision
    assert a.reason_codes == b.reason_codes
    assert a.recommended_profile == b.recommended_profile
    assert a.freshness_tier == b.freshness_tier
    assert a.salary_tier == b.salary_tier


def test_linkedin_saved_search_url_rejected():
    assert is_saved_search_url("https://www.linkedin.com/jobs/search/?keywords=tpm")
    result = evaluate_eligibility(
        _base(url="https://www.linkedin.com/jobs/search/?keywords=tpm&location=United%20States")
    )
    assert result.decision == DECISION_REJECT
    assert SAVED_SEARCH_URL_NOT_JOB_URL in result.reason_codes


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
    loc, reason, *_ = evaluate_location(
        {
            "title": "Remote Software Engineer",
            "location": "Remote (India)",
            "description_text": "Work from India. Bangalore preferred.",
        }
    )
    assert loc == INELIGIBLE_FOREIGN


# --- Domain exclusion: non-software (manufacturing / pharma / hardware) QE roles ---
def test_pharma_gmp_quality_engineering_rejected_by_domain():
    """A QE title at a pharma manufacturer (GMP) must reject despite the title match."""
    result = evaluate_eligibility(
        _base(
            title="Director, Quality Engineering",
            company="Catalent Inc",
            location="Saint Petersburg, FL",
            description_text=(
                "range of pharmaceutical products. Director, Quality Engineering to lead "
                "strategic GMP initiatives in a regulated manufacturing facility."
            ),
        )
    )
    assert result.decision == DECISION_REJECT, result.reasons
    assert result.owner_visible is False
    assert any("domain" in r.lower() for r in result.reasons), result.reasons


def test_industrial_product_quality_rejected_by_domain():
    """Industrial 'high-quality products and services' quality role must reject."""
    result = evaluate_eligibility(
        _base(
            title="Director Quality Engineering",
            company="Honeywell",
            location="Atlanta, GA",
            description_text=(
                "As a Director of Quality Engineering you will drive the consistent "
                "delivery of high-quality products and services and quality excellence."
            ),
        )
    )
    assert result.decision == DECISION_REJECT, result.reasons
    assert result.owner_visible is False


def test_software_quality_engineering_still_accepted():
    """A genuine software QE role with the same title must remain accepted."""
    result = evaluate_eligibility(
        _base(
            title="Director, Quality Engineering",
            company="Reveal Technology",
            location="New York, NY",
            description_text=(
                "Own the overarching test automation infrastructure and scale a lean team "
                "of QA engineers to deliver software quality across our platform."
            ),
        )
    )
    assert result.decision == DECISION_ACCEPT, result.reasons
    assert result.owner_visible is True


def test_air_quality_title_rejected_despite_qe_profile():
    """'Air Quality Engineer' must reject even though it resembles a QE title."""
    result = evaluate_eligibility(
        _base(title="Principal Air Quality Engineer", company="Poutrix", location="United States")
    )
    assert result.decision == DECISION_REJECT, result.reasons
    assert result.owner_visible is False


def test_design_quality_engineering_title_rejected():
    result = evaluate_eligibility(
        _base(
            title="Quality Manager - Design Quality Engineering",
            company="Wapa",
            location="United States",
            description_text="Lead a team of Design Quality Engineers providing guidance.",
        )
    )
    assert result.decision == DECISION_REJECT, result.reasons
    assert result.owner_visible is False


def test_supplier_quality_in_html_description_rejected():
    """HTML tags in the description must not defeat the domain phrase match."""
    result = evaluate_eligibility(
        _base(
            title="Principal Quality Engineer",
            company="Westinghouse Electric",
            location="United States",
            description_text=(
                "As a Principal Supplier <b>Quality Engineer</b> you will lead quality "
                "assurance tasks for Large Structures in the AP1000 nuclear product line."
            ),
        )
    )
    assert result.decision == DECISION_REJECT, result.reasons
    assert result.owner_visible is False


def test_domain_reject_requires_contiguous_phrase():
    """'manufacturing' and 'quality' far apart must NOT trigger the domain reject."""
    result = evaluate_eligibility(
        _base(
            title="Senior Manager, Quality Engineering",
            company="Acme Software",
            description_text=(
                "We build manufacturing analytics software. You will own quality "
                "engineering and test automation for our cloud platform."
            ),
        )
    )
    assert result.decision == DECISION_ACCEPT, result.reasons


# --- Canonical owner decision model: persisted dedupe/override reconciliation ---
# Regression for the Workflow Lock 01 audit-vs-canonical 12-vs-11 discrepancy: a
# syndicated near-duplicate that the stateless single-row engine re-accepts must be
# folded back to DUPLICATE by the canonical decision model, matching persisted eligibility.


def test_evaluate_owner_decision_accepts_clean_software_qe_role():
    from app.services.job_eligibility import evaluate_owner_decision

    result = evaluate_owner_decision(
        _base(
            title="Senior Manager, Quality Engineering",
            company="Blockstream",
            description_text="Lead software quality engineering and test automation for our platform.",
        )
    )
    assert result.decision == DECISION_ACCEPT, result.reasons
    assert result.owner_visible is True


def test_evaluate_owner_decision_honors_persisted_syndicated_duplicate():
    from app.services.job_eligibility import DUPLICATE_SYNDICATED, evaluate_owner_decision

    # Engine alone would ACCEPT this fresh software QA-manager role, but production
    # persisted it as a syndicated duplicate (different provider id/URL, same role/company).
    payload = _base(
        external_id="syndicated-2",
        title="Remote QA Engineering Manager for Blockchain & FinTech",
        company="Blockstream",
        description_text="Lead software quality engineering and test automation across teams.",
        persisted_ingest_decision=DECISION_REJECT,
        persisted_reason_codes=[DUPLICATE_SYNDICATED],
    )
    engine_only = evaluate_eligibility(payload)
    assert engine_only.decision == DECISION_ACCEPT  # stateless engine re-accepts

    canonical = evaluate_owner_decision(payload)
    assert canonical.decision == "DUPLICATE"
    assert canonical.owner_visible is False
    assert DUPLICATE_SYNDICATED in canonical.reason_codes


def test_evaluate_owner_decision_no_persisted_disposition_is_engine_result():
    from app.services.job_eligibility import evaluate_owner_decision

    payload = _base(title="Senior Manager, Quality Engineering", company="Acme")
    assert evaluate_owner_decision(payload).decision == evaluate_eligibility(payload).decision
