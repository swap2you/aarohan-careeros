"""Parse job-alert emails from major boards into normalized job payloads."""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parseaddr
from urllib.parse import parse_qs, urlparse

JOB_ALERT_LABEL_PREFIX = "Aarohan/Job Alerts"


@dataclass
class ParsedJobAlert:
    source: str
    external_id: str
    title: str
    company: str
    location: str | None
    url: str
    description_text: str
    confidence: float


def _extract_url(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0) if match else None


def _linkedin(message: dict) -> ParsedJobAlert | None:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    url = _extract_url(body, r"https?://(?:www\.)?linkedin\.com/[^\s\"'>]+")
    if not url:
        return None
    title_match = re.search(r"(?:new jobs?|job alert|match).*?:\s*(.+)", message.get("subject", ""), re.I)
    title = title_match.group(1).strip() if title_match else "LinkedIn job alert"
    company_match = re.search(r"at\s+([A-Za-z0-9&.,' -]{2,80})", body)
    company = company_match.group(1).strip() if company_match else "Unknown employer"
    loc_match = re.search(r"(?:location|in)\s*:\s*([^\n|]+)", body, re.I)
    external_id = urlparse(url).path.rstrip("/").split("/")[-1] or url
    return ParsedJobAlert(
        source="linkedin_alert_emails",
        external_id=external_id[:255],
        title=title[:512],
        company=company[:255],
        location=loc_match.group(1).strip()[:255] if loc_match else None,
        url=url[:1024],
        description_text=body[:8000],
        confidence=0.85,
    )


def _indeed(message: dict) -> ParsedJobAlert | None:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    url = _extract_url(body, r"https?://(?:www\.)?indeed\.com/[^\s\"'>]+")
    if not url:
        return None
    title = message.get("subject", "Indeed job alert").replace("Indeed", "").strip(" :-")[:512]
    company_match = re.search(r"company\s*:\s*([^\n|]+)", body, re.I)
    company = company_match.group(1).strip() if company_match else "Unknown employer"
    loc_match = re.search(r"location\s*:\s*([^\n|]+)", body, re.I)
    parsed = urlparse(url)
    jk = parse_qs(parsed.query).get("jk", [parsed.path.split("/")[-1]])[0]
    return ParsedJobAlert(
        source="indeed_alert_emails",
        external_id=str(jk)[:255],
        title=title or "Indeed job alert",
        company=company[:255],
        location=loc_match.group(1).strip()[:255] if loc_match else None,
        url=url[:1024],
        description_text=body[:8000],
        confidence=0.82,
    )


def _dice(message: dict) -> ParsedJobAlert | None:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    url = _extract_url(body, r"https?://(?:www\.)?dice\.com/[^\s\"'>]+")
    if not url:
        return None
    title_match = re.search(r"^([^|]+)", message.get("subject", ""))
    title = title_match.group(1).strip() if title_match else "Dice job alert"
    company_match = re.search(r"with\s+([A-Za-z0-9&.,' -]{2,80})", body, re.I)
    company = company_match.group(1).strip() if company_match else "Unknown employer"
    external_id = urlparse(url).path.rstrip("/").split("/")[-1] or url
    return ParsedJobAlert(
        source="dice_alert_emails",
        external_id=external_id[:255],
        title=title[:512],
        company=company[:255],
        location=None,
        url=url[:1024],
        description_text=body[:8000],
        confidence=0.8,
    )


def _glassdoor(message: dict) -> ParsedJobAlert | None:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    url = _extract_url(body, r"https?://(?:www\.)?glassdoor\.com/[^\s\"'>]+")
    if not url:
        return None
    title = message.get("subject", "Glassdoor job alert")[:512]
    company_match = re.search(r"at\s+([A-Za-z0-9&.,' -]{2,80})", body, re.I)
    company = company_match.group(1).strip() if company_match else "Unknown employer"
    external_id = urlparse(url).path.rstrip("/").split("/")[-1] or url
    return ParsedJobAlert(
        source="glassdoor_alert_emails",
        external_id=external_id[:255],
        title=title,
        company=company[:255],
        location=None,
        url=url[:1024],
        description_text=body[:8000],
        confidence=0.78,
    )


def _usajobs(message: dict) -> ParsedJobAlert | None:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    url = _extract_url(body, r"https?://(?:www\.)?usajobs\.gov/[^\s\"'>]+")
    if not url:
        return None
    title = message.get("subject", "USAJOBS alert")[:512]
    agency_match = re.search(r"agency\s*:\s*([^\n|]+)", body, re.I)
    company = agency_match.group(1).strip() if agency_match else "US Federal"
    control = re.search(r"(\d{10,})", url + body)
    external_id = control.group(1) if control else urlparse(url).path.rstrip("/").split("/")[-1]
    return ParsedJobAlert(
        source="usajobs_alert_emails",
        external_id=str(external_id)[:255],
        title=title,
        company=company[:255],
        location=None,
        url=url[:1024],
        description_text=body[:8000],
        confidence=0.83,
    )


_PARSERS_BY_LABEL: dict[str, callable] = {
    "Aarohan/Job Alerts/LinkedIn": _linkedin,
    "Aarohan/Job Alerts/Indeed": _indeed,
    "Aarohan/Job Alerts/Dice": _dice,
    "Aarohan/Job Alerts/Glassdoor": _glassdoor,
    "Aarohan/Job Alerts/USAJOBS": _usajobs,
}


def parse_job_alert(message: dict, *, label: str | None = None) -> ParsedJobAlert | None:
    if label and label in _PARSERS_BY_LABEL:
        return _PARSERS_BY_LABEL[label](message)
    sender = parseaddr(message.get("sender", ""))[1].lower()
    subject = (message.get("subject") or "").lower()
    if "linkedin" in sender or "linkedin" in subject:
        return _linkedin(message)
    if "indeed" in sender or "indeed" in subject:
        return _indeed(message)
    if "dice" in sender or "dice" in subject:
        return _dice(message)
    if "glassdoor" in sender or "glassdoor" in subject:
        return _glassdoor(message)
    if "usajobs" in sender or "usajobs" in subject:
        return _usajobs(message)
    return None


def parsed_job_to_ingest_payload(alert: ParsedJobAlert) -> dict:
    return {
        "source": alert.source,
        "external_id": alert.external_id,
        "title": alert.title,
        "company": alert.company,
        "location": alert.location,
        "url": alert.url,
        "description_text": alert.description_text,
        "description_html": f"<p>{alert.description_text[:2000]}</p>",
    }
