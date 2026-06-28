import re
from html import unescape

import bleach


ALLOWED_TAGS: list[str] = []
ALLOWED_ATTRIBUTES: dict = {}


def sanitize_html(value: str) -> str:
    cleaned = bleach.clean(value or "", tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    return unescape(cleaned)


def html_to_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()
