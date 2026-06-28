from datetime import datetime, timedelta

import httpx

from app.services.config_loader import source_policy


class GreenhouseAdapter:
    source_name = "greenhouse_public_get"

    def __init__(self, board_token: str):
        self.board_token = board_token
        self.base_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

    def is_allowed(self) -> bool:
        return self.source_name in source_policy().get("allowed_automated", [])

    def fetch_jobs(self) -> list[dict]:
        if not self.is_allowed():
            raise PermissionError("Greenhouse adapter is not allowed by source policy.")
        with httpx.Client(timeout=30.0) as client:
            response = client.get(self.base_url, params={"content": "true"})
            response.raise_for_status()
            payload = response.json()
        jobs = []
        for item in payload.get("jobs", []):
            location = item.get("location", {}).get("name")
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": str(item["id"]),
                    "title": item.get("title", ""),
                    "company": self.board_token,
                    "location": location,
                    "description_html": item.get("content", ""),
                    "url": item.get("absolute_url", ""),
                    "posted_at": item.get("updated_at"),
                    "workplace_type": None,
                }
            )
        return jobs


class LeverAdapter:
    source_name = "lever_public_get"

    def __init__(self, company_slug: str):
        self.company_slug = company_slug
        self.base_url = f"https://api.lever.co/v0/postings/{company_slug}"

    def is_allowed(self) -> bool:
        return self.source_name in source_policy().get("allowed_automated", [])

    def fetch_jobs(self) -> list[dict]:
        if not self.is_allowed():
            raise PermissionError("Lever adapter is not allowed by source policy.")
        with httpx.Client(timeout=30.0) as client:
            response = client.get(self.base_url, params={"mode": "json"})
            response.raise_for_status()
            payload = response.json()
        jobs = []
        for item in payload:
            jobs.append(
                {
                    "source": self.source_name,
                    "external_id": item.get("id", ""),
                    "title": item.get("text", ""),
                    "company": self.company_slug,
                    "location": (item.get("categories") or {}).get("location"),
                    "description_html": item.get("descriptionPlain", ""),
                    "description_text": item.get("descriptionPlain", ""),
                    "url": item.get("hostedUrl", ""),
                    "posted_at": datetime.utcfromtimestamp(item["createdAt"] / 1000).isoformat()
                    if item.get("createdAt")
                    else None,
                    "workplace_type": (item.get("categories") or {}).get("commitment"),
                }
            )
        return jobs


class FixtureFeedAdapter:
    source_name = "approved_remote_feeds"

    def is_allowed(self) -> bool:
        return self.source_name in source_policy().get("allowed_automated", [])

    def fetch_jobs(self) -> list[dict]:
        if not self.is_allowed():
            raise PermissionError("Fixture feed is not allowed by source policy.")
        now = datetime.utcnow()
        return [
            {
                "source": self.source_name,
                "external_id": "fixture-remote-qe-001",
                "title": "Director of Quality Engineering",
                "company": "Example Health Tech",
                "location": "Remote, US",
                "workplace_type": "fully_remote_us",
                "salary_min": 190000,
                "salary_max": 230000,
                "description_html": "<p>Lead enterprise quality engineering transformation, automation platform architecture, API and performance testing, CI/CD quality gates, test platform governance, GenAI and agentic AI evaluation.</p>",
                "description_text": "Lead enterprise quality engineering transformation, automation platform architecture, API and performance testing, CI/CD quality gates, test platform governance, GenAI and agentic AI evaluation. Director-level leadership scope.",
                "url": "https://example.com/jobs/director-qe",
                "posted_at": (now - timedelta(hours=6)).isoformat(),
            }
        ]
