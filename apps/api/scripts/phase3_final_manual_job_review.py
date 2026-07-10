#!/usr/bin/env python3
"""Manual review and correction of accepted candidate jobs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Job, WorkflowState
from app.services.job_eligibility import (
    DECISION_ACCEPT,
    DECISION_OWNER_REVIEW,
    DECISION_REJECT,
    TIER_HISTORICAL,
    evaluate_eligibility,
    evaluate_freshness,
)
from app.services.provenance import PROVENANCE_VALIDATION
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity
from app.services.title_normalization import normalize_title, pattern_in_title
from app.services.sanitize import html_to_text

NON_SOFTWARE_QUALITY_PATTERNS = [
    "air quality",
    "supplier quality",
    "environmental quality",
    "manufacturing quality",
    "hardware quality",
    "product inspection",
    "design quality engineering",
    "quality inspector",
    "quality technician",
    "quality control inspector",
]

SYNDICATION_HOSTS = {
    "jooble.org",
    "virtualvocations.com",
    "onlinejobs.ph",
    "learn4good.com",
}

SOFTWARE_QUALITY_SIGNALS = [
    "software quality",
    "quality engineering",
    "qa engineering",
    "test automation",
    "quality platform",
    "quality assurance engineering",
    "sdet",
    "quality manager",
    "director quality",
    "head of quality",
    "principal quality engineer",
]


def _canonical_employer(company: str) -> str:
    c = re.sub(r"[^a-z0-9]+", " ", (company or "").lower()).strip()
    for suffix in (" inc", " llc", " ltd", " corporation", " corp"):
        if c.endswith(suffix):
            c = c[: -len(suffix)].strip()
    return c


def _url_host(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _is_syndicated(url: str) -> bool:
    host = _url_host(url)
    return any(marker in host for marker in SYNDICATION_HOSTS)


def _plain_text(title: str, description: str) -> str:
    return f"{title} {html_to_text(description or '')}".lower()


def _is_non_software_quality(title: str, description: str) -> tuple[bool, str | None]:
    text = _plain_text(title, description)
    for pattern in NON_SOFTWARE_QUALITY_PATTERNS:
        if pattern_in_title(pattern, title) or pattern in text:
            if pattern == "design quality engineering":
                if not any(sig in text for sig in ("software", "digital", "saas", "platform", "automation")):
                    return True, f"non_software_quality:{pattern}"
            else:
                return True, f"non_software_quality:{pattern}"
    if "quality" in text and not any(sig in text for sig in SOFTWARE_QUALITY_SIGNALS):
        if any(k in text for k in ("supplier", "manufacturing", "environmental", "air ", "hardware")):
            return True, "non_software_quality:context"
    return False, None


def _dedupe_key(job: Job) -> tuple[str, str, str]:
    title = normalize_title(job.title)
    employer = _canonical_employer(job.company)
    if employer == "blockstream" and "qa" in title and "manager" in title:
        title = "qa engineering manager"
    return (employer, title, (job.location or "").lower()[:40])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual accepted job review")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--apply", action="store_true", default=True)
    args = parser.parse_args(argv)

    if not args.database_url:
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    now = datetime.utcnow()
    accepted: list[dict] = []
    owner_review: list[dict] = []
    rejected_false_positives: list[dict] = []
    duplicate_dispositions: list[dict] = []

    try:
        jobs = (
            db.query(Job)
            .filter(Job.data_provenance != PROVENANCE_VALIDATION)
            .filter(Job.eligible_for_owner.is_(True))
            .order_by(Job.id)
            .all()
        )

        groups: dict[tuple[str, str, str], list[Job]] = {}
        for job in jobs:
            groups.setdefault(_dedupe_key(job), []).append(job)

        keep_ids: set[int] = set()
        for key, group in groups.items():
            if len(group) == 1:
                keep_ids.add(group[0].id)
                continue
            ranked = sorted(
                group,
                key=lambda j: (
                    _is_syndicated(j.url or ""),
                    0 if (j.url or "").startswith("https://") else 1,
                    j.id,
                ),
            )
            keeper = ranked[0]
            keep_ids.add(keeper.id)
            for dup in ranked[1:]:
                duplicate_dispositions.append({
                    "kept_job_id": keeper.id,
                    "rejected_job_id": dup.id,
                    "title": dup.title,
                    "company": dup.company,
                    "url": dup.url,
                    "reason": "duplicate_syndicated_copy",
                })
                if args.apply:
                    dup.eligible_for_owner = False
                    dup.ingest_decision = DECISION_REJECT
                    dup.ingest_reason_codes = ["DUPLICATE_SYNDICATED"]
                    dup.ingest_reasons = ["Superseded by canonical employer listing"]
                    dup.state = WorkflowState.REJECTED.value
                    db.add(dup)

        for job in jobs:
            if job.id not in keep_ids:
                continue

            payload = {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "description_text": job.description_text,
                "source": job.source,
                "posted_at": job.posted_at,
                "source_received_at": job.source_received_at,
                "discovered_at": job.discovered_at,
            }
            tier, ts_source, effective_at, age_hours, _, _, _, _ = evaluate_freshness(payload, now=now)
            eligibility = evaluate_eligibility(payload, now=now)

            non_sw, non_sw_reason = _is_non_software_quality(job.title, job.description_text or "")
            entry = {
                "job_id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "official_url": job.url,
                "source": job.source,
                "timestamp_source": ts_source or job.freshness_source,
                "age_hours": age_hours,
                "freshness_tier": tier or job.freshness_bucket,
                "role_profile": job.recommended_profile or eligibility.recommended_profile,
                "reason_codes": list(eligibility.reason_codes),
                "acceptance_reason": "; ".join(eligibility.reasons) if eligibility.reasons else "policy_match",
                "duplicate_disposition": "canonical",
            }

            final_decision = eligibility.decision
            if tier == TIER_HISTORICAL:
                final_decision = DECISION_REJECT
                entry["reason_codes"].append("STALE_OVER_7_DAYS")
                entry["acceptance_reason"] = "Job older than 7-day Fresh Jobs window"
            elif non_sw:
                final_decision = DECISION_REJECT
                entry["reason_codes"].append(non_sw_reason or "NON_SOFTWARE_QUALITY")
                rejected_false_positives.append({**entry, "rejection_reason": non_sw_reason})
            elif not job.url:
                final_decision = DECISION_REJECT
                entry["reason_codes"].append("MISSING_OFFICIAL_URL")
            elif eligibility.decision != DECISION_ACCEPT:
                final_decision = eligibility.decision

            entry["final_decision"] = final_decision

            if args.apply:
                job.ingest_reason_codes = entry["reason_codes"]
                job.ingest_reasons = [entry.get("acceptance_reason", "")]
                job.freshness_bucket = tier or job.freshness_bucket
                if final_decision == DECISION_ACCEPT:
                    job.eligible_for_owner = True
                    job.ingest_decision = DECISION_ACCEPT
                    accepted.append(entry)
                elif final_decision == DECISION_OWNER_REVIEW:
                    job.eligible_for_owner = False
                    job.ingest_decision = DECISION_OWNER_REVIEW
                    owner_review.append(entry)
                else:
                    job.eligible_for_owner = False
                    job.ingest_decision = DECISION_REJECT
                    job.state = WorkflowState.REJECTED.value
                db.add(job)
            else:
                if final_decision == DECISION_ACCEPT:
                    accepted.append(entry)
                elif final_decision == DECISION_OWNER_REVIEW:
                    owner_review.append(entry)
                else:
                    rejected_false_positives.append(entry)

        if args.apply:
            db.commit()

        for entry in accepted:
            if not entry.get("official_url"):
                entry["validation_error"] = "missing_official_url"
        passed = all(
            e.get("official_url") and e.get("freshness_tier") not in {None, TIER_HISTORICAL}
            for e in accepted
        )
    finally:
        db.close()
        engine.dispose()

    report = {
        "generated_at": now.isoformat(),
        "accepted": accepted,
        "owner_review": owner_review,
        "rejected_false_positives": rejected_false_positives,
        "duplicate_dispositions": duplicate_dispositions,
        "counts": {
            "accepted": len(accepted),
            "owner_review": len(owner_review),
            "rejected_false_positives": len(rejected_false_positives),
            "duplicates_removed": len(duplicate_dispositions),
        },
        "passed": passed and not any(e.get("validation_error") for e in accepted),
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({"accepted": len(accepted), "passed": report["passed"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
