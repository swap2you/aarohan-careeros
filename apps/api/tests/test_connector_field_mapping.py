"""Connector field mapping — USAJOBS location must not truncate."""

from app.integrations.job_providers import _usajobs_location, _usajobs_publication_start


def test_usajobs_location_joins_full_strings():
    meta = {
        "PositionLocationDisplay": ["Atlanta, Georgia", "Washington, District of Columbia"],
    }
    loc = _usajobs_location(meta)
    assert loc is not None
    assert len(loc) > 1
    assert "Atlanta" in loc
    assert "Washington" in loc


def test_usajobs_location_from_structured():
    meta = {
        "PositionLocation": [
            {"CityName": "Northford", "CountrySubDivisionCode": "CT", "CountryCode": "United States"},
        ]
    }
    loc = _usajobs_location(meta)
    assert "Northford" in loc
    assert "CT" in loc
    assert len(loc) > 1


def test_usajobs_ignores_single_character_display():
    meta = {"PositionLocationDisplay": ["n", "m", "r"]}
    loc = _usajobs_location(meta)
    assert loc is None


def test_usajobs_publication_start():
    meta = {"PublicationStartDate": "2026-07-08T00:00:00"}
    assert _usajobs_publication_start(meta) == "2026-07-08T00:00:00"
