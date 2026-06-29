"""Detect ATS provider from official application URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class AtsProvider(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    UNSUPPORTED = "unsupported"
    PROHIBITED = "prohibited"


PROHIBITED_HOST_PATTERNS = (
    r"linkedin\.com",
    r"indeed\.com",
    r"glassdoor\.com",
    r"dice\.com",
)

SUPPORTED_PATTERNS: dict[AtsProvider, tuple[str, ...]] = {
    AtsProvider.GREENHOUSE: (
        r"boards\.greenhouse\.io",
        r"job-boards\.greenhouse\.io",
        r"greenhouse\.io/.+/jobs/",
    ),
    AtsProvider.LEVER: (
        r"jobs\.lever\.co",
        r"lever\.co/.+/",
    ),
    AtsProvider.ASHBY: (
        r"jobs\.ashbyhq\.com",
        r"ashbyhq\.com/.+/application",
    ),
}


@dataclass
class AtsDetectionResult:
    provider: AtsProvider
    supported: bool
    assisted_available: bool
    official_url: str
    host: str
    summary: str
    fallback_mode: str

    def to_dict(self) -> dict:
        return {
            "provider": self.provider.value,
            "supported": self.supported,
            "assisted_available": self.assisted_available,
            "official_url": self.official_url,
            "host": self.host,
            "summary": self.summary,
            "fallback_mode": self.fallback_mode,
        }


def detect_ats(url: str) -> AtsDetectionResult:
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    full = f"{host}{parsed.path}".lower()

    for pattern in PROHIBITED_HOST_PATTERNS:
        if re.search(pattern, host) or re.search(pattern, full):
            return AtsDetectionResult(
                provider=AtsProvider.PROHIBITED,
                supported=False,
                assisted_available=False,
                official_url=url,
                host=host,
                summary="Applications on this site must use Manual mode only.",
                fallback_mode="MANUAL",
            )

    for provider, patterns in SUPPORTED_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, host) or re.search(pattern, full):
                label = provider.value.title()
                return AtsDetectionResult(
                    provider=provider,
                    supported=True,
                    assisted_available=True,
                    official_url=url,
                    host=host,
                    summary=f"{label}-hosted application detected. Assisted mode can prepare fields and stop before submit.",
                    fallback_mode="ASSISTED",
                )

    return AtsDetectionResult(
        provider=AtsProvider.UNSUPPORTED,
        supported=False,
        assisted_available=False,
        official_url=url,
        host=host,
        summary="This application site is not in the assisted support list. Use Manual mode.",
        fallback_mode="MANUAL",
    )
