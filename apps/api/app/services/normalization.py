import hashlib
import re


def normalize_company(name: str) -> str:
    value = (name or "").lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(title: str) -> str:
    value = (title or "").lower().strip()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def build_dedupe_key(company: str, title: str, location: str | None = None) -> str:
    parts = [normalize_company(company), normalize_title(title)]
    if location:
        parts.append(location.lower().strip())
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_salary_range(text: str) -> tuple[int | None, int | None]:
    if not text:
        return None, None
    amounts = [int(match.replace(",", "")) for match in re.findall(r"\$?\s?(\d{2,3}(?:,\d{3})+|\d{5,6})", text)]
    if not amounts:
        return None, None
    if len(amounts) == 1:
        return amounts[0], amounts[0]
    return min(amounts), max(amounts)


def detect_workplace_type(text: str) -> str:
    lowered = (text or "").lower()
    if "fully remote" in lowered or "100% remote" in lowered or "remote - us" in lowered:
        return "fully_remote_us"
    if "remote" in lowered and "hybrid" not in lowered:
        return "remote"
    if "hybrid" in lowered:
        return "hybrid"
    if "relocation" in lowered or "on-site only" in lowered or "onsite only" in lowered:
        return "mandatory_relocation"
    return "unknown"
