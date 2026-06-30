"""Data provenance for owner vs test/fixture isolation."""

from __future__ import annotations

PROVENANCE_LIVE = "live"
PROVENANCE_FIXTURE = "fixture"
PROVENANCE_TEST = "test"
PROVENANCE_GMAIL = "gmail"
PROVENANCE_CONNECTOR = "connector"
PROVENANCE_MANUAL = "manual"

OWNER_EXCLUDED = {PROVENANCE_FIXTURE, PROVENANCE_TEST}

FIXTURE_SOURCES = frozenset(
    {
        "fixture",
        "fixture_feed",
        "gmail_fixture",
        "test",
        "e2e",
    }
)

CONNECTOR_SOURCES = frozenset(
    {
        "greenhouse",
        "lever",
        "ashby",
        "remotive",
        "remoteok",
        "adzuna",
        "jooble",
        "usajobs",
        "rss",
        "public_feed",
    }
)


def infer_provenance(source: str, *, explicit: str | None = None, payload: dict | None = None) -> str:
    if explicit:
        return explicit
    if payload:
        ext = (payload.get("external_id") or "").lower()
        if ext.startswith("e2e-") or ext.startswith("e2e_"):
            return PROVENANCE_TEST
        url = (payload.get("url") or "").lower()
        if "/e2e/" in url or "example.com/e2e" in url:
            return PROVENANCE_TEST
        req = payload.get("requisition_id") or ""
        if str(req).startswith("REQ-E2E-"):
            return PROVENANCE_TEST
    normalized = (source or "").lower().strip()
    if normalized in FIXTURE_SOURCES or "fixture" in normalized or normalized.startswith("test_"):
        return PROVENANCE_FIXTURE
    if normalized.startswith("gmail"):
        return PROVENANCE_GMAIL
    if normalized in CONNECTOR_SOURCES:
        return PROVENANCE_CONNECTOR
    if normalized in {"manual", "url_import", "forwarded"}:
        return PROVENANCE_MANUAL
    return PROVENANCE_LIVE


def is_owner_visible(provenance: str | None) -> bool:
    return (provenance or PROVENANCE_LIVE) not in OWNER_EXCLUDED
