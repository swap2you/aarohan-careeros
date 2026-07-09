"""Canonical job-title normalization shared by ingest, audit, scoring, and opportunities."""

from __future__ import annotations

import re
import unicodedata


def normalize_title(value: str | None) -> str:
    """Lowercase, strip punctuation to spaces, collapse whitespace.

    Used for role-profile matching so commas, dashes, ampersands, and
    parentheses do not prevent target-title recognition.
    """
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def title_tokens(value: str | None) -> list[str]:
    return [t for t in normalize_title(value).split(" ") if t]


def _expand_manager_variants(tokens: list[str]) -> list[list[str]]:
    """Support singular/plural manager variants where appropriate."""
    variants = [tokens]
    if "managers" in tokens:
        variants.append(["manager" if t == "managers" else t for t in tokens])
    if "manager" in tokens:
        variants.append(["managers" if t == "manager" else t for t in tokens])
    # Deduplicate while preserving order
    seen: set[tuple[str, ...]] = set()
    out: list[list[str]] = []
    for v in variants:
        key = tuple(v)
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def pattern_in_title(pattern: str, title: str) -> bool:
    """True when normalized pattern tokens appear in order in the normalized title.

    Allows intervening tokens so "Director, Quality Engineering & Platform Reliability"
    still matches "director quality engineering".
    """
    pattern_tokens = title_tokens(pattern)
    title_toks = title_tokens(title)
    if not pattern_tokens or not title_toks:
        return False

    for variant in _expand_manager_variants(pattern_tokens):
        if _tokens_in_order(variant, title_toks):
            return True
    return False


def _tokens_in_order(needle: list[str], haystack: list[str]) -> bool:
    if not needle:
        return False
    # Contiguous phrase first (preferred)
    n = len(needle)
    for i in range(len(haystack) - n + 1):
        if haystack[i : i + n] == needle:
            return True
    # Ordered subsequence for compound titles with extra scope words
    # (e.g. "director quality engineering" inside "... platform reliability")
    if len(needle) < 2:
        return False
    idx = 0
    for token in haystack:
        if token == needle[idx]:
            idx += 1
            if idx == len(needle):
                return True
    return False
