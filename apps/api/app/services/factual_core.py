"""Resume factual-core hash and consistency validation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.career_vault import public_evidence_statements


@dataclass
class FactualCoreResult:
    hash: str
    consistent: bool
    unchanged_facts: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    new_claims: list[str] = field(default_factory=list)
    indicator: str = "No known conflict"

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "consistent": self.consistent,
            "unchanged_facts": self.unchanged_facts,
            "contradictions": self.contradictions,
            "new_claims": self.new_claims,
            "indicator": self.indicator,
        }


def _normalize_fact(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def build_factual_core(db: Session) -> list[str]:
    return sorted(public_evidence_statements(db))


def compute_factual_core_hash(facts: list[str]) -> str:
    payload = json.dumps([_normalize_fact(f) for f in facts], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def validate_factual_core(
    db: Session,
    *,
    resume_text: str,
    prior_hash: str | None = None,
) -> FactualCoreResult:
    facts = build_factual_core(db)
    core_hash = compute_factual_core_hash(facts)
    resume_lower = resume_text.lower()
    unchanged: list[str] = []
    contradictions: list[str] = []

    for fact in facts:
        tokens = [t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]{2,}", fact.lower()) if len(t) > 4]
        if not tokens:
            continue
        anchor = tokens[0]
        if anchor in resume_lower:
            unchanged.append(fact)
        elif any(token in resume_lower for token in tokens[:3]):
            unchanged.append(fact)

    if prior_hash and prior_hash != core_hash:
        contradictions.append(
            "Approved career record changed since the last packet; factual core hash mismatch."
        )

    consistent = not contradictions
    indicator = "No known conflict" if consistent else "Resume consistency issue"
    return FactualCoreResult(
        hash=core_hash,
        consistent=consistent,
        unchanged_facts=unchanged[:20],
        contradictions=contradictions,
        new_claims=[],
        indicator=indicator,
    )
