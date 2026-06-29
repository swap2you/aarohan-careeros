"""ATS detection tests."""

from app.services.ats_detection import AtsProvider, detect_ats


def test_greenhouse_detection():
    result = detect_ats("https://boards.greenhouse.io/acme/jobs/12345")
    assert result.provider == AtsProvider.GREENHOUSE
    assert result.assisted_available is True


def test_lever_detection():
    result = detect_ats("https://jobs.lever.co/acme/abc-123")
    assert result.provider == AtsProvider.LEVER
    assert result.assisted_available is True


def test_ashby_detection():
    result = detect_ats("https://jobs.ashbyhq.com/acme/role-123/application")
    assert result.provider == AtsProvider.ASHBY
    assert result.assisted_available is True


def test_linkedin_prohibited():
    result = detect_ats("https://www.linkedin.com/jobs/view/123")
    assert result.provider == AtsProvider.PROHIBITED
    assert result.fallback_mode == "MANUAL"


def test_indeed_prohibited():
    result = detect_ats("https://www.indeed.com/viewjob?jk=abc")
    assert result.provider == AtsProvider.PROHIBITED


def test_unsupported_workday_fallback():
    result = detect_ats("https://acme.wd5.myworkdayjobs.com/en-US/careers/job/123")
    assert result.provider == AtsProvider.UNSUPPORTED
    assert result.fallback_mode == "MANUAL"
