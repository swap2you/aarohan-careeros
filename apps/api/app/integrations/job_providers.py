"""Job discovery provider interface and registry."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

from app.config import settings
from app.services.config_loader import source_policy


class ConnectorState(str, Enum):
    READY = "READY"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DISABLED = "DISABLED"
    PENDING_APPROVAL = "PENDING_APPROVAL"


@dataclass
class ProviderStatus:
    provider_id: str
    label: str
    state: ConnectorState
    source_name: str
    requires_api_key: bool = False
    attribution: str | None = None
    rate_limit_hint: str | None = None
    message: str | None = None
    last_run_at: datetime | None = None
    last_job_count: int | None = None

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "label": self.label,
            "state": self.state.value,
            "source_name": self.source_name,
            "requires_api_key": self.requires_api_key,
            "attribution": self.attribution,
            "rate_limit_hint": self.rate_limit_hint,
            "message": self.message,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_job_count": self.last_job_count,
        }


@dataclass
class FetchResult:
    jobs: list[dict] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)


def _http_get(url: str, *, params: dict | None = None, headers: dict | None = None) -> dict | list:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params, headers=headers or {})
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    raise last_error or RuntimeError("HTTP request failed")


def _http_post(url: str, *, json_body: dict, headers: dict | None = None) -> dict | list:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=json_body, headers=headers or {})
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    raise last_error or RuntimeError("HTTP request failed")


def _policy_allows(source_name: str) -> bool:
    policy = source_policy()
    return source_name in policy.get("allowed_automated", [])


class JobProvider(ABC):
    provider_id: str
    label: str
    source_name: str
    requires_api_key: bool = False
    attribution: str | None = None
    rate_limit_hint: str | None = None

    def base_status(self) -> ProviderStatus:
        if not _policy_allows(self.source_name):
            return ProviderStatus(
                provider_id=self.provider_id,
                label=self.label,
                state=ConnectorState.DISABLED,
                source_name=self.source_name,
                requires_api_key=self.requires_api_key,
                attribution=self.attribution,
                rate_limit_hint=self.rate_limit_hint,
                message="Blocked by source policy",
            )
        if self.requires_api_key and not self.is_configured():
            return ProviderStatus(
                provider_id=self.provider_id,
                label=self.label,
                state=ConnectorState.NOT_CONFIGURED,
                source_name=self.source_name,
                requires_api_key=True,
                attribution=self.attribution,
                rate_limit_hint=self.rate_limit_hint,
                message="API credentials not configured",
            )
        return ProviderStatus(
            provider_id=self.provider_id,
            label=self.label,
            state=ConnectorState.READY,
            source_name=self.source_name,
            requires_api_key=self.requires_api_key,
            attribution=self.attribution,
            rate_limit_hint=self.rate_limit_hint,
        )

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def fetch_jobs(self, **params: Any) -> FetchResult:
        ...

    def fixture_jobs(self) -> list[dict]:
        return []


class GreenhouseProvider(JobProvider):
    provider_id = "greenhouse"
    label = "Greenhouse"
    source_name = "greenhouse_public_get"
    rate_limit_hint = "Public board API; use sparingly"

    def is_configured(self) -> bool:
        return True

    def fetch_jobs(self, **params: Any) -> FetchResult:
        board_token = params.get("board_token")
        if not board_token:
            raise ValueError("board_token required")
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
        payload = _http_get(url, params={"content": "true"})
        jobs = []
        for item in payload.get("jobs", []):
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": str(item["id"]),
                    "title": item.get("title", ""),
                    "company": board_token,
                    "location": (item.get("location") or {}).get("name"),
                    "description_html": item.get("content", ""),
                    "url": item.get("absolute_url", ""),
                    "posted_at": item.get("updated_at"),
                    "ats_job_id": str(item["id"]),
                }
            )
        return FetchResult(jobs=jobs, provenance={"board_token": board_token, "provider": self.provider_id})

    def fixture_jobs(self) -> list[dict]:
        return [
            {
                "source": self.source_name,
                "external_id": "gh-fixture-1",
                "title": "Staff Quality Engineer",
                "company": "fixture-board",
                "location": "Remote",
                "description_text": "Greenhouse fixture job",
                "url": "https://example.com/greenhouse/fixture",
                "posted_at": datetime.utcnow().isoformat(),
                "ats_job_id": "gh-fixture-1",
            }
        ]


class LeverProvider(JobProvider):
    provider_id = "lever"
    label = "Lever"
    source_name = "lever_public_get"

    def is_configured(self) -> bool:
        return True

    def fetch_jobs(self, **params: Any) -> FetchResult:
        slug = params.get("company_slug")
        if not slug:
            raise ValueError("company_slug required")
        url = f"https://api.lever.co/v0/postings/{slug}"
        payload = _http_get(url, params={"mode": "json"})
        jobs = []
        for item in payload:
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": item.get("id", ""),
                    "title": item.get("text", ""),
                    "company": slug,
                    "location": (item.get("categories") or {}).get("location"),
                    "description_text": item.get("descriptionPlain", ""),
                    "url": item.get("hostedUrl", ""),
                    "posted_at": datetime.utcfromtimestamp(item["createdAt"] / 1000).isoformat()
                    if item.get("createdAt")
                    else None,
                    "ats_job_id": item.get("id"),
                }
            )
        return FetchResult(jobs=jobs, provenance={"company_slug": slug, "provider": self.provider_id})

    def fixture_jobs(self) -> list[dict]:
        return [
            {
                "source": self.source_name,
                "external_id": "lever-fixture-1",
                "title": "Director QE",
                "company": "fixture-co",
                "location": "Remote, US",
                "description_text": "Lever fixture job",
                "url": "https://example.com/lever/fixture",
                "posted_at": datetime.utcnow().isoformat(),
            }
        ]


class AshbyProvider(JobProvider):
    provider_id = "ashby"
    label = "Ashby"
    source_name = "ashby_public_get"
    attribution = "Ashby public job posting API"

    def is_configured(self) -> bool:
        return True

    def fetch_jobs(self, **params: Any) -> FetchResult:
        board = params.get("job_board_name")
        if not board:
            raise ValueError("job_board_name required")
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
        payload = _http_get(url)
        jobs = []
        for item in payload.get("jobs", []):
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": item.get("id", ""),
                    "title": item.get("title", ""),
                    "company": board,
                    "location": item.get("location", ""),
                    "description_html": item.get("descriptionHtml", ""),
                    "description_text": item.get("descriptionPlain", ""),
                    "url": item.get("jobUrl", ""),
                    "posted_at": item.get("publishedAt"),
                    "ats_job_id": item.get("id"),
                }
            )
        return FetchResult(jobs=jobs, provenance={"job_board_name": board, "provider": self.provider_id})

    def fixture_jobs(self) -> list[dict]:
        return [
            {
                "source": self.source_name,
                "external_id": "ashby-fixture-1",
                "title": "QE Platform Architect",
                "company": "fixture-ashby",
                "location": "Hybrid",
                "description_text": "Ashby fixture job",
                "url": "https://example.com/ashby/fixture",
            }
        ]


class RemotiveProvider(JobProvider):
    provider_id = "remotive"
    label = "Remotive"
    source_name = "remotive_public_get"
    attribution = "Remotive remote jobs API"

    def is_configured(self) -> bool:
        return True

    def fetch_jobs(self, **params: Any) -> FetchResult:
        category = params.get("category", "software-dev")
        url = "https://remotive.com/api/remote-jobs"
        payload = _http_get(url, params={"category": category})
        jobs = []
        for item in payload.get("jobs", [])[:50]:
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": str(item.get("id", "")),
                    "title": item.get("title", ""),
                    "company": item.get("company_name", "Remotive"),
                    "location": item.get("candidate_required_location", "Remote"),
                    "description_html": item.get("description", ""),
                    "description_text": item.get("description", ""),
                    "url": item.get("url", ""),
                    "posted_at": item.get("publication_date"),
                    "salary_min": _parse_int(item.get("salary_min")),
                    "salary_max": _parse_int(item.get("salary_max")),
                }
            )
        return FetchResult(jobs=jobs, provenance={"category": category, "provider": self.provider_id})

    def fixture_jobs(self) -> list[dict]:
        return [
            {
                "source": self.source_name,
                "external_id": "remotive-fixture-1",
                "title": "Remote QA Lead",
                "company": "Remotive Fixture Co",
                "location": "Remote",
                "description_text": "Remotive fixture job",
                "url": "https://example.com/remotive/fixture",
            }
        ]


class RemoteOkProvider(JobProvider):
    provider_id = "remote_ok"
    label = "Remote OK"
    source_name = "remote_ok_public_get"
    attribution = "Remote OK public API"

    def is_configured(self) -> bool:
        return True

    def fetch_jobs(self, **params: Any) -> FetchResult:
        url = "https://remoteok.com/api"
        payload = _http_get(url, headers={"User-Agent": "AarohanCareOS/1.0 (personal use)"})
        jobs = []
        for item in payload[1:51] if isinstance(payload, list) else []:
            if not isinstance(item, dict):
                continue
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": str(item.get("id", "")),
                    "title": item.get("position", ""),
                    "company": item.get("company", "Remote OK"),
                    "location": item.get("location", "Remote"),
                    "description_html": item.get("description", ""),
                    "description_text": item.get("description", ""),
                    "url": item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id')}",
                    "posted_at": item.get("date"),
                }
            )
        return FetchResult(jobs=jobs, provenance={"provider": self.provider_id})

    def fixture_jobs(self) -> list[dict]:
        return [
            {
                "source": self.source_name,
                "external_id": "remoteok-fixture-1",
                "title": "Remote SDET",
                "company": "Remote OK Fixture",
                "location": "Remote",
                "description_text": "Remote OK fixture job",
                "url": "https://example.com/remoteok/fixture",
            }
        ]


class RssFeedProvider(JobProvider):
    provider_id = "rss"
    label = "Approved RSS"
    source_name = "approved_rss_feeds"

    def is_configured(self) -> bool:
        return bool(settings.rss_feed_urls.strip())

    def fetch_jobs(self, **params: Any) -> FetchResult:
        import xml.etree.ElementTree as ET

        feed_url = params.get("feed_url") or settings.rss_feed_urls.split(",")[0].strip()
        if not feed_url:
            raise ValueError("RSS feed URL not configured")
        with httpx.Client(timeout=30.0) as client:
            response = client.get(feed_url)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        jobs = []
        for item in root.findall(".//item")[:30]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
            guid = (item.findtext("guid") or link or title)[:128]
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": guid,
                    "title": title,
                    "company": params.get("company", "RSS Feed"),
                    "location": params.get("location"),
                    "description_html": description,
                    "description_text": description,
                    "url": link,
                }
            )
        return FetchResult(jobs=jobs, provenance={"feed_url": feed_url, "provider": self.provider_id})

    def fixture_jobs(self) -> list[dict]:
        return [
            {
                "source": self.source_name,
                "external_id": "rss-fixture-1",
                "title": "RSS Fixture Role",
                "company": "RSS Publisher",
                "location": "Remote",
                "description_text": "RSS fixture job",
                "url": "https://example.com/rss/fixture",
            }
        ]


class AdzunaProvider(JobProvider):
    provider_id = "adzuna"
    label = "Adzuna"
    source_name = "adzuna_api"
    requires_api_key = True
    attribution = "Jobs by Adzuna — retain attribution and original links"

    def is_configured(self) -> bool:
        return bool(settings.adzuna_app_id and settings.adzuna_app_key)

    def fetch_jobs(self, **params: Any) -> FetchResult:
        if not self.is_configured():
            raise ValueError("Adzuna API credentials not configured")
        country = params.get("country", "us")
        what = params.get("what", "quality engineering director")
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        payload = _http_get(
            url,
            params={
                "app_id": settings.adzuna_app_id,
                "app_key": settings.adzuna_app_key,
                "what": what,
                "results_per_page": 20,
            },
        )
        jobs = []
        for item in payload.get("results", []):
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": str(item.get("id", "")),
                    "title": item.get("title", ""),
                    "company": item.get("company", {}).get("display_name", "Adzuna"),
                    "location": item.get("location", {}).get("display_name"),
                    "description_text": item.get("description", ""),
                    "url": item.get("redirect_url", ""),
                    "salary_min": _parse_int((item.get("salary_min"))),
                    "salary_max": _parse_int((item.get("salary_max"))),
                }
            )
        return FetchResult(
            jobs=jobs,
            provenance={"provider": self.provider_id, "attribution": self.attribution, "what": what},
        )

    def fixture_jobs(self) -> list[dict]:
        return [
            {
                "source": self.source_name,
                "external_id": "adzuna-fixture-1",
                "title": "Director Quality Engineering",
                "company": "Adzuna Fixture Corp",
                "location": "Remote, US",
                "description_text": "Adzuna fixture job — attribution required",
                "url": "https://example.com/adzuna/fixture",
            }
        ]


class JoobleProvider(JobProvider):
    provider_id = "jooble"
    label = "Jooble"
    source_name = "jooble_api"
    requires_api_key = True
    attribution = "Jooble job search API"

    def is_configured(self) -> bool:
        return bool(settings.jooble_api_key)

    def fetch_jobs(self, **params: Any) -> FetchResult:
        if not self.is_configured():
            raise ValueError("Jooble API key not configured")
        keywords = params.get("keywords", "quality engineering director remote")
        url = f"https://jooble.org/api/{settings.jooble_api_key}"
        payload = _http_post(url, json_body={"keywords": keywords, "page": "1"})
        jobs = []
        for item in payload.get("jobs", [])[:20]:
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": str(item.get("id") or item.get("link", ""))[:128],
                    "title": item.get("title", ""),
                    "company": item.get("company", "Jooble"),
                    "location": item.get("location"),
                    "description_text": item.get("snippet", ""),
                    "url": item.get("link", ""),
                }
            )
        return FetchResult(jobs=jobs, provenance={"provider": self.provider_id, "keywords": keywords})

    def fixture_jobs(self) -> list[dict]:
        return [
            {
                "source": self.source_name,
                "external_id": "jooble-fixture-1",
                "title": "QE Director",
                "company": "Jooble Fixture",
                "location": "Remote",
                "description_text": "Jooble fixture job",
                "url": "https://example.com/jooble/fixture",
            }
        ]


class UsajobsProvider(JobProvider):
    provider_id = "usajobs"
    label = "USAJOBS"
    source_name = "usajobs_api"
    requires_api_key = True
    attribution = "USAJOBS Open Data API"

    def is_configured(self) -> bool:
        return bool(settings.usajobs_api_key and settings.usajobs_user_email)

    def fetch_jobs(self, **params: Any) -> FetchResult:
        if not self.is_configured():
            raise ValueError("USAJOBS API key and user email not configured")
        keyword = params.get("keyword", "quality assurance")
        url = "https://data.usajobs.gov/api/search"
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                url,
                params={"Keyword": keyword, "ResultsPerPage": 20},
                headers={
                    "Host": "data.usajobs.gov",
                    "User-Agent": settings.usajobs_user_email,
                    "Authorization-Key": settings.usajobs_api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
        jobs = []
        for item in payload.get("SearchResult", {}).get("SearchResultItems", []):
            meta = item.get("MatchedObjectDescriptor", {})
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": meta.get("PositionID", ""),
                    "title": meta.get("PositionTitle", ""),
                    "company": meta.get("OrganizationName", "US Government"),
                    "location": _usajobs_location(meta),
                    "description_text": meta.get("UserArea", {}).get("Details", {}).get("MajorDuties", [""])[0],
                    "url": meta.get("PositionURI", ""),
                    "requisition_id": meta.get("PositionID"),
                }
            )
        return FetchResult(jobs=jobs, provenance={"provider": self.provider_id, "keyword": keyword})

    def fixture_jobs(self) -> list[dict]:
        return [
            {
                "source": self.source_name,
                "external_id": "usajobs-fixture-1",
                "title": "IT Specialist (QA)",
                "company": "US Fixture Agency",
                "location": "Washington, DC",
                "description_text": "USAJOBS fixture job",
                "url": "https://example.com/usajobs/fixture",
            }
        ]


class FixtureFeedProvider(JobProvider):
    provider_id = "fixture"
    label = "Approved Remote Fixture"
    source_name = "approved_remote_feeds"

    def is_configured(self) -> bool:
        return True

    def fetch_jobs(self, **params: Any) -> FetchResult:
        from app.integrations.job_sources import FixtureFeedAdapter

        jobs = FixtureFeedAdapter().fetch_jobs()
        return FetchResult(jobs=jobs, provenance={"provider": self.provider_id, "fixture": True})

    def fixture_jobs(self) -> list[dict]:
        return self.fetch_jobs().jobs


def _parse_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _usajobs_location(meta: dict) -> str | None:
    locations = meta.get("PositionLocationDisplay", [])
    if locations:
        return locations[0]
    return None


PROVIDER_REGISTRY: dict[str, JobProvider] = {
    p.provider_id: p
    for p in [
        FixtureFeedProvider(),
        GreenhouseProvider(),
        LeverProvider(),
        AshbyProvider(),
        RemotiveProvider(),
        RemoteOkProvider(),
        RssFeedProvider(),
        AdzunaProvider(),
        JoobleProvider(),
        UsajobsProvider(),
    ]
}


def list_provider_statuses() -> list[ProviderStatus]:
    return [provider.base_status() for provider in PROVIDER_REGISTRY.values()]


def get_provider(provider_id: str) -> JobProvider:
    provider = PROVIDER_REGISTRY.get(provider_id)
    if not provider:
        raise KeyError(f"Unknown provider: {provider_id}")
    return provider
