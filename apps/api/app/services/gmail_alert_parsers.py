"""Parse job-alert emails from major boards into normalized job payloads."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parseaddr
from urllib.parse import parse_qs, urlparse, urlunparse

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

BAD_TITLES = {
    "linkedin job alert",
    "indeed job alert",
    "job alert",
    "your job alert",
    "linkedin role",
    "indeed role",
    "new jobs matching your alert",
    "see all jobs",
}

BAD_COMPANY_FRAGMENTS = (
    "match your interests",
    "penndot",
    "update your preferences",
    "manage alert",
    "unsubscribe",
    "email preferences",
    "job alert",
    "linkedin",
    "indeed",
)


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
    gmail_message_id: str | None = None
    gmail_thread_id: str | None = None
    source_label: str | None = None
    received_at: datetime | str | None = None


def canonical_job_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if "linkedin.com" in parsed.netloc.lower():
        path = parsed.path.split("?")[0].rstrip("/")
        m = re.search(r"/jobs/view/(\d+)", path)
        if m:
            return f"https://www.linkedin.com/jobs/view/{m.group(1)}"
        return urlunparse((parsed.scheme or "https", "www.linkedin.com", path, "", "", ""))
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


def _window_around(text: str, needle: str, radius: int = 280) -> str:
    idx = text.find(needle)
    if idx < 0:
        return text[:radius]
    return text[max(0, idx - radius) : idx + len(needle) + radius]


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", (title or "").strip(" -\t|"))
    if not title or title.lower() in BAD_TITLES:
        return ""
    if len(title) < 4 or len(title) > 160:
        return ""
    return title


def _clean_company(company: str) -> str:
    company = re.sub(r"\s+", " ", (company or "").strip(" -\t|.,"))
    lowered = company.lower()
    if not company or any(frag in lowered for frag in BAD_COMPANY_FRAGMENTS):
        return ""
    if len(company) < 2 or len(company) > 120:
        return ""
    # Reject sentence-like footers
    if company.count(" ") > 8 or company.endswith("."):
        return ""
    return company


def _extract_title_company(window: str) -> tuple[str, str]:
    # Prefer "Title at Company" / "Title @ Company" near the URL
    patterns = [
        r"([A-Za-z0-9][^\n|]{3,100}?)\s+(?:at|@)\s+([A-Za-z0-9][A-Za-z0-9&.,'()\- ]{1,80})",
        r"(?:^|\n)\s*([A-Za-z0-9][^\n|]{3,100}?)\s*\n\s*([A-Za-z0-9][A-Za-z0-9&.,'()\- ]{1,80})\s*\n",
    ]
    for pattern in patterns:
        match = re.search(pattern, window, re.I)
        if not match:
            continue
        title = _clean_title(match.group(1))
        company = _clean_company(match.group(2))
        if title:
            return title, company
    return "", ""


def _extract_location(window: str) -> str | None:
    loc_match = re.search(
        r"(?:location|in)\s*:\s*([^\n|]{2,120})",
        window,
        re.I,
    )
    if loc_match:
        loc = loc_match.group(1).strip()
        if len(loc) > 1:
            return loc[:255]
    # City, ST pattern
    city_state = re.search(
        r"\b([A-Z][a-zA-Z .'-]+,\s*(?:[A-Z]{2}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)(?:,\s*United States)?)\b",
        window,
    )
    if city_state:
        return city_state.group(1).strip()[:255]
    return None


def _linkedin_entries(message: dict, *, label: str | None = None) -> list[ParsedJobAlert]:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    urls = _extract_urls(body, r"https?://(?:www\.)?linkedin\.com/jobs/view/\d+[^\s\"'<>]*")
    if not urls:
        return []
    alerts: list[ParsedJobAlert] = []
    seen_ids: set[str] = set()
    for raw_url in urls:
        url = canonical_job_url(raw_url)
        m = re.search(r"/jobs/view/(\d+)", url)
        if not m:
            continue
        external_id = m.group(1)
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)
        window = _window_around(body, raw_url)
        title, company = _extract_title_company(window)
        location = _extract_location(window)
        snippet = window.strip()[:1200]
        confidence = 0.9 if title and company else (0.7 if title else 0.4)
        alerts.append(
            ParsedJobAlert(
                source="linkedin_alert_emails",
                external_id=external_id[:255],
                title=(title or "UNPARSED_LINKEDIN_ENTRY")[:512],
                company=(company or "Unknown employer")[:255],
                location=location,
                url=url[:1024],
                description_text=snippet,
                confidence=confidence,
                provider_job_id=external_id,
                gmail_message_id=message.get("gmail_message_id") or message.get("id"),
                gmail_thread_id=message.get("gmail_thread_id") or message.get("thread_id"),
                source_label=label or "Aarohan/Job Alerts/LinkedIn",
                received_at=message.get("received_at") or message.get("internalDate"),
            )
        )
    return alerts


def _indeed_entries(message: dict, *, label: str | None = None) -> list[ParsedJobAlert]:
    body = f"{message.get('subject', '')}\n{message.get('body_text', '')}"
    urls = _extract_urls(body, r"https?://(?:www\.)?indeed\.com/[^\s\"'<>]+")
    if not urls:
        return []
    alerts: list[ParsedJobAlert] = []
    seen: set[str] = set()
    for raw_url in urls:
        if "/viewjob" not in raw_url.lower() and "jk=" not in raw_url.lower():
            continue
        url = canonical_job_url(raw_url)
        parsed = urlparse(url)
        jk = parse_qs(parsed.query).get("jk", [None])[0]
        if not jk or jk in seen:
            continue
        seen.add(jk)
        window = _window_around(body, raw_url)
        title, company = _extract_title_company(window)
        if not title:
            # Do not fall back to digest subject ("3 new ... jobs" / "Indeed job alert")
            title = ""
        location = _extract_location(window)
        confidence = 0.88 if title and company else (0.65 if title else 0.4)
        alerts.append(
            ParsedJobAlert(
                source="indeed_alert_emails",
                external_id=str(jk)[:255],
                title=(title or "UNPARSED_INDEED_ENTRY")[:512],
                company=(company or "Unknown employer")[:255],
                location=location,
                url=url[:1024],
                description_text=window.strip()[:1200],
                confidence=confidence,
                provider_job_id=str(jk),
                gmail_message_id=message.get("gmail_message_id") or message.get("id"),
                gmail_thread_id=message.get("gmail_thread_id") or message.get("thread_id"),
                source_label=label or "Aarohan/Job Alerts/Indeed",
                received_at=message.get("received_at") or message.get("internalDate"),
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
    title = _clean_title(title_match.group(1) if title_match else "") or "Dice role"
    company_match = re.search(r"with\s+([A-Za-z0-9&.,' -]{2,80})", body, re.I)
    company = _clean_company(company_match.group(1) if company_match else "") or "Unknown employer"
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
    title = _clean_title(message.get("subject", "")) or "Glassdoor role"
    company_match = re.search(r"at\s+([A-Za-z0-9&.,' -]{2,80})", body, re.I)
    company = _clean_company(company_match.group(1) if company_match else "") or "Unknown employer"
    external_id = urlparse(url).path.rstrip("/").split("/")[-1] or url
    return ParsedJobAlert(
        source="glassdoor_alert_emails",
        external_id=external_id[:255],
        title=title[:512],
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
    title = _clean_title(message.get("subject", "")) or "USAJOBS role"
    agency_match = re.search(r"agency\s*:\s*([^\n|]+)", body, re.I)
    company = _clean_company(agency_match.group(1) if agency_match else "") or "US Federal"
    control = re.search(r"(\d{10,})", url + body)
    external_id = control.group(1) if control else urlparse(url).path.rstrip("/").split("/")[-1]
    return ParsedJobAlert(
        source="usajobs_alert_emails",
        external_id=str(external_id)[:255],
        title=title[:512],
        company=company[:255],
        location=None,
        url=url[:1024],
        description_text=_window_around(body, urls[0])[:1200],
        confidence=0.83,
        provider_job_id=str(external_id),
    )


_PARSERS_BY_LABEL: dict[str, callable] = {
    "Aarohan/Job Alerts/LinkedIn": lambda m: _linkedin_entries(m, label="Aarohan/Job Alerts/LinkedIn"),
    "Aarohan/Job Alerts/Indeed": lambda m: _indeed_entries(m, label="Aarohan/Job Alerts/Indeed"),
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
        return _linkedin_entries(message, label=label)
    if "indeed" in sender or "indeed" in subject:
        return _indeed_entries(message, label=label)
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


def parsed_job_to_ingest_payload(
    alert: ParsedJobAlert,
    *,
    gmail_message_id: str | None = None,
    source_received_at: str | datetime | None = None,
    gmail_thread_id: str | None = None,
    source_label: str | None = None,
) -> dict:
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
    received = source_received_at if source_received_at is not None else alert.received_at
    if received is not None:
        if isinstance(received, datetime):
            payload["source_received_at"] = received.isoformat()
            payload["received_at"] = received.isoformat()
        else:
            # Gmail internalDate may be epoch ms
            if isinstance(received, (int, float)) or (isinstance(received, str) and str(received).isdigit()):
                try:
                    ms = int(received)
                    if ms > 1_000_000_000_000:
                        dt = datetime.utcfromtimestamp(ms / 1000.0)
                    else:
                        dt = datetime.utcfromtimestamp(ms)
                    payload["source_received_at"] = dt.isoformat()
                    payload["received_at"] = dt.isoformat()
                except (OverflowError, OSError, ValueError):
                    payload["source_received_at"] = str(received)
                    payload["received_at"] = str(received)
            else:
                payload["source_received_at"] = received
                payload["received_at"] = received
    raw: dict = {}
    mid = gmail_message_id or alert.gmail_message_id
    tid = gmail_thread_id or alert.gmail_thread_id
    label = source_label or alert.source_label
    if mid:
        raw["gmail_message_id"] = mid
    if tid:
        raw["gmail_thread_id"] = tid
    if label:
        raw["source_label"] = label
    if raw:
        payload["raw_payload"] = raw
    return payload
