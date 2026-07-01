"""Parse job-alert emails from major boards into normalized job payloads."""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parseaddr
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

JOB_ALERT_LABEL_PREFIX = "Aarohan/Job Alerts"

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "trk",
    "trackingId",
    "refId",
    "lipi",
    "midToken",
    "midSig",
    "eBP",
}


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
    provider_job_id: str | None = None


def canonical_job_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if "linkedin.com" in parsed.netloc.lower():
        path = parsed.path.split("?")[0].rstrip("/")
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    if "indeed.com" in parsed.netloc.lower():
        qs = parse_qs(parsed.query)
        jk = qs.get("jk", [None])[0]
        if jk:
            return f"https://www.indeed.com/viewjob?jk={jk}"
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    clean_qs = [(k, v) for k, v in parse_qs(parsed.query).items() if k not in TRACKING_PARAMS]
    query = "&".join(f"{k}={v[0]}" for k, v in clean_qs)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", query, ""))


def _extract_urls(text: str, pattern: str) -> list[str]:
    return list(dict.fromkeys(re.findall(pattern, text, re.IGNORECASE)))


def _window_around(text: str, needle: str, radius: int = 220) -> str:
    idx = text.find(needle)
    if idx < 0:
        return text[:radius]
    return text[max(0, idx - radius) : idx + radius]


def _linkedin_entries(message: dict) -> list[ParsedJobAlert]:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    urls = _extract_urls(body, r"https?://(?:www\.)?linkedin\.com/jobs/view/\d+[^\s\"'<>]*")
    if not urls:
        return []
    alerts: list[ParsedJobAlert] = []
    for raw_url in urls:
        url = canonical_job_url(raw_url)
        external_id = url.rstrip("/").split("/")[-1]
        window = _window_around(body, raw_url)
        title_match = re.search(
            r"([A-Za-z0-9][^\n|]{4,90}?)\s+(?:at|@)\s+([A-Za-z0-9&.,'()\- ]{2,80})",
            window,
            re.I,
        )
        title = title_match.group(1).strip() if title_match else "LinkedIn role"
        company = title_match.group(2).strip() if title_match else "Unknown employer"
        loc_match = re.search(r"(?:location|in)\s*:\s*([^\n|]+)", window, re.I)
        snippet = window.strip()[:1200]
        alerts.append(
            ParsedJobAlert(
                source="linkedin_alert_emails",
                external_id=external_id[:255],
                title=title[:512],
                company=company[:255],
                location=loc_match.group(1).strip()[:255] if loc_match else None,
                url=url[:1024],
                description_text=snippet,
                confidence=0.88 if title_match else 0.62,
                provider_job_id=external_id,
            )
        )
    return alerts


def _indeed_entries(message: dict) -> list[ParsedJobAlert]:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    urls = _extract_urls(body, r"https?://(?:www\.)?indeed\.com/[^\s\"'<>]+")
    if not urls:
        return []
    alerts: list[ParsedJobAlert] = []
    for raw_url in urls:
        if "/viewjob" not in raw_url.lower() and "jk=" not in raw_url.lower():
            continue
        url = canonical_job_url(raw_url)
        parsed = urlparse(url)
        jk = parse_qs(parsed.query).get("jk", [parsed.path.split("/")[-1]])[0]
        window = _window_around(body, raw_url)
        title_match = re.search(r"([A-Za-z0-9][^\n|]{4,90}?)\s+(?:at|@)\s+([A-Za-z0-9&.,'()\- ]{2,80})", window, re.I)
        title = title_match.group(1).strip() if title_match else message.get("subject", "Indeed role")[:512]
        company = title_match.group(2).strip() if title_match else "Unknown employer"
        loc_match = re.search(r"location\s*:\s*([^\n|]+)", window, re.I)
        alerts.append(
            ParsedJobAlert(
                source="indeed_alert_emails",
                external_id=str(jk)[:255],
                title=title[:512],
                company=company[:255],
                location=loc_match.group(1).strip()[:255] if loc_match else None,
                url=url[:1024],
                description_text=window.strip()[:1200],
                confidence=0.86 if title_match else 0.6,
                provider_job_id=str(jk),
            )
        )
    return alerts


def _linkedin(message: dict) -> ParsedJobAlert | None:
    entries = _linkedin_entries(message)
    return entries[0] if entries else None


def _indeed(message: dict) -> ParsedJobAlert | None:
    entries = _indeed_entries(message)
    return entries[0] if entries else None


def _dice(message: dict) -> ParsedJobAlert | None:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    urls = _extract_urls(body, r"https?://(?:www\.)?dice\.com/[^\s\"'<>]+")
    if not urls:
        return None
    url = canonical_job_url(urls[0])
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
        description_text=_window_around(body, urls[0])[:1200],
        confidence=0.8,
        provider_job_id=external_id,
    )


def _glassdoor(message: dict) -> ParsedJobAlert | None:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    urls = _extract_urls(body, r"https?://(?:www\.)?glassdoor\.com/[^\s\"'<>]+")
    if not urls:
        return None
    url = canonical_job_url(urls[0])
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
        description_text=_window_around(body, urls[0])[:1200],
        confidence=0.78,
        provider_job_id=external_id,
    )


def _usajobs(message: dict) -> ParsedJobAlert | None:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    urls = _extract_urls(body, r"https?://(?:www\.)?usajobs\.gov/[^\s\"'<>]+")
    if not urls:
        return None
    url = canonical_job_url(urls[0])
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
        description_text=_window_around(body, urls[0])[:1200],
        confidence=0.83,
        provider_job_id=str(external_id),
    )


_PARSERS_BY_LABEL: dict[str, callable] = {
    "Aarohan/Job Alerts/LinkedIn": _linkedin_entries,
    "Aarohan/Job Alerts/Indeed": _indeed_entries,
    "Aarohan/Job Alerts/Dice": lambda m: [_dice(m)] if _dice(m) else [],
    "Aarohan/Job Alerts/Glassdoor": lambda m: [_glassdoor(m)] if _glassdoor(m) else [],
    "Aarohan/Job Alerts/USAJOBS": lambda m: [_usajobs(m)] if _usajobs(m) else [],
}


def parse_job_alerts(message: dict, *, label: str | None = None) -> list[ParsedJobAlert]:
    if label and label in _PARSERS_BY_LABEL:
        return _PARSERS_BY_LABEL[label](message)
    sender = parseaddr(message.get("sender", ""))[1].lower()
    subject = (message.get("subject") or "").lower()
    if "linkedin" in sender or "linkedin" in subject:
        return _linkedin_entries(message)
    if "indeed" in sender or "indeed" in subject:
        return _indeed_entries(message)
    if "dice" in sender or "dice" in subject:
        one = _dice(message)
        return [one] if one else []
    if "glassdoor" in sender or "glassdoor" in subject:
        one = _glassdoor(message)
        return [one] if one else []
    if "usajobs" in sender or "usajobs" in subject:
        one = _usajobs(message)
        return [one] if one else []
    return []


def parse_job_alert(message: dict, *, label: str | None = None) -> ParsedJobAlert | None:
    alerts = parse_job_alerts(message, label=label)
    return alerts[0] if alerts else None


def parsed_job_to_ingest_payload(alert: ParsedJobAlert, *, gmail_message_id: str | None = None) -> dict:
    payload = {
        "source": alert.source,
        "external_id": alert.external_id,
        "title": alert.title,
        "company": alert.company,
        "location": alert.location,
        "url": alert.url,
        "description_text": alert.description_text,
        "description_html": f"<p>{alert.description_text[:2000]}</p>",
        "requisition_id": alert.provider_job_id,
    }
    if gmail_message_id:
        payload["raw_payload"] = {"gmail_message_id": gmail_message_id}
    return payload
