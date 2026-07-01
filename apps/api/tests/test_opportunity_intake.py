"""Tests for ad hoc opportunity intake."""

from app.services.opportunity_intake import extract_opportunity, parse_job_fields, recommend_profiles


def test_parse_job_fields_from_text():
    text = """
    Title: Senior Technical Project Manager
    Company: Acme Corp
    Location: Remote - US
    Salary: $160,000 - $190,000 per year
  Requisition ID: REQ-12345
    Lead cross-functional engineering delivery.
    """
    fields = parse_job_fields(text=text, url="https://www.linkedin.com/jobs/view/123")
    assert fields["title"] == "Senior Technical Project Manager"
    assert fields["company"] == "Acme Corp"
    assert fields["source"] == "linkedin"
    assert fields["salary_min"] == 160000
    assert fields["salary_max"] in (160000, 190000)
    assert fields["requisition_id"] == "REQ-12345"


def test_recommend_profiles_prefers_tpm():
    recs = recommend_profiles(
        "Senior Technical Program Manager",
        "engineering program delivery quality platforms",
    )
    assert recs[0]["profile_id"] == "tpm_delivery"


def test_extract_requires_confirmation():
    result = extract_opportunity(
        plain_text="Title: QE Manager\nCompany: Beta LLC\nLead quality engineering teams.",
    )
    assert result["requires_confirmation"] is True
    assert result["extracted"]["company"] == "Beta LLC"
    assert result["recommended_profiles"]


def test_extract_opportunity_api(client, auth_headers):
    response = client.post(
        "/api/opportunities/extract",
        headers=auth_headers,
        json={
            "plain_text": "Title: Principal Quality Engineer\nCompany: Gamma Inc\nRemote hybrid role.",
            "url": "https://boards.greenhouse.io/gamma/jobs/1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["extracted"]["source"] == "greenhouse"
    assert body["extracted"]["title"] == "Principal Quality Engineer"


def test_confirm_opportunity_creates_job(client, auth_headers):
    extract = client.post(
        "/api/opportunities/extract",
        headers=auth_headers,
        json={"plain_text": "Title: TPM\nCompany: Delta Co\nProgram delivery for QE platforms."},
    ).json()
    response = client.post(
        "/api/opportunities/confirm",
        headers=auth_headers,
        json={"extracted": extract["extracted"], "generate_packet": False},
    )
    assert response.status_code == 200
    assert response.json()["job_id"] > 0
