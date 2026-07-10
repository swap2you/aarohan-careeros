#!/usr/bin/env python3
"""Validate owner candidate database integrity after Phase 3 import."""

from __future__ import annotations

import argparse
import json
import os
import sys

from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker

from app.models import (
    Application,
    ApplicationDocumentVersion,
    Company,
    Job,
    OAuthToken,
    ProcessedGmailMessage,
    User,
)
from app.services.provenance import OWNER_EXCLUDED
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity

E2E_EMAIL = "e2e@test.local"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3 owner candidate validation")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    defects: list[dict] = []
    checks: dict[str, bool | int | dict] = {}

    try:
        checks["users"] = db.query(User).count()
        checks["jobs"] = db.query(Job).count()
        checks["applications"] = db.query(Application).count()
        checks["oauth_tokens"] = db.query(OAuthToken).count()
        checks["processed_gmail_messages"] = db.query(ProcessedGmailMessage).count()

        e2e_users = db.query(User).filter(func.lower(User.email) == E2E_EMAIL).count()
        if e2e_users:
            defects.append({"severity": "critical", "check": "no_e2e_users", "detail": f"found {e2e_users}"})

        fixture_jobs = 0
        if hasattr(Job, "data_provenance"):
            fixture_jobs = db.query(Job).filter(Job.data_provenance.in_(OWNER_EXCLUDED)).count()
        if fixture_jobs:
            defects.append({"severity": "high", "check": "no_fixture_jobs", "detail": f"found {fixture_jobs}"})

        orphaned_apps = (
            db.query(Application)
            .outerjoin(Job, Application.job_id == Job.id)
            .filter(Job.id.is_(None))
            .count()
        )
        if orphaned_apps:
            defects.append({"severity": "critical", "check": "no_orphan_applications", "detail": str(orphaned_apps)})

        orphaned_docs = (
            db.query(ApplicationDocumentVersion)
            .outerjoin(Application, ApplicationDocumentVersion.application_id == Application.id)
            .filter(Application.id.is_(None))
            .count()
        )
        if orphaned_docs:
            defects.append({"severity": "high", "check": "no_orphan_document_versions", "detail": str(orphaned_docs)})

        dup_oauth = (
            db.query(OAuthToken.provider, OAuthToken.service, OAuthToken.account_email, func.count())
            .group_by(OAuthToken.provider, OAuthToken.service, OAuthToken.account_email)
            .having(func.count() > 1)
            .count()
        )
        if dup_oauth:
            defects.append({"severity": "high", "check": "no_duplicate_oauth", "detail": str(dup_oauth)})

        dup_gmail = (
            db.query(ProcessedGmailMessage.message_id, func.count())
            .group_by(ProcessedGmailMessage.message_id)
            .having(func.count() > 1)
            .count()
        )
        if dup_gmail:
            defects.append({"severity": "high", "check": "no_duplicate_gmail_ids", "detail": str(dup_gmail)})

        orphan_companies = (
            db.query(Company)
            .outerjoin(Job, Job.company_id == Company.id)
            .filter(Job.id.is_(None))
            .count()
        )
        if orphan_companies and db.query(Job).count() == 0:
            defects.append({
                "severity": "medium",
                "check": "orphan_companies_without_jobs",
                "detail": str(orphan_companies),
            })

        marker = db.execute(
            text(
                "SELECT purpose, identity_uuid FROM aarohan_meta.database_identity ORDER BY id LIMIT 1"
            )
        ).one()
        checks["identity_marker"] = {"purpose": marker.purpose, "identity_uuid": str(marker.identity_uuid)}
    finally:
        db.close()
        engine.dispose()

    result = {
        "checks": checks,
        "defects": defects,
        "passed": not defects,
    }
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(json.dumps({"passed": result["passed"], "defect_count": len(defects)}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
