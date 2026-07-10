#!/usr/bin/env python3
"""Resolve existing Aarohan Drive root on candidate without creating a new root."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import SystemSetting
from app.services.drive_settings import (
    APP_DRIVE_ROOT_FOLDER_NAME,
    DRIVE_ACTIVE_ROOT_KEY,
    DRIVE_ROOT_SOURCE_KEY,
    DRIVE_SUBFOLDERS,
    DRIVE_SUBFOLDERS_KEY,
    is_drive_folder_accessible,
)
from app.services.google_api import _auth_headers, get_token
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity


def _get_setting(db, key: str) -> str | None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).one_or_none()
    return row.value if row else None


def _find_app_roots(token_data: dict) -> list[dict]:
    query = (
        f"name='{APP_DRIVE_ROOT_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=_auth_headers(token_data),
            params={
                "q": query,
                "fields": "files(id,name,appProperties,owners,createdTime)",
                "pageSize": 20,
            },
        )
    if resp.status_code != 200:
        return []
    return resp.json().get("files", [])


def _verify_subfolders(token_data: dict, root_id: str, expected: dict[str, str] | None) -> dict:
    if not expected:
        return {"present": [], "missing": DRIVE_SUBFOLDERS, "complete": False}
    present = []
    missing = []
    for name in DRIVE_SUBFOLDERS:
        if name in expected and expected[name]:
            if is_drive_folder_accessible(token_data, expected[name]):
                present.append(name)
            else:
                missing.append(name)
        else:
            missing.append(name)
    return {"present": present, "missing": missing, "complete": not missing}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drive root resolution for candidate")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1
    if settings.oauth_fixture_mode:
        print("Refusing drive resolution in fixture mode", file=sys.stderr)
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    result: dict = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "resolution_method": None,
        "folder_id": None,
        "accessible": False,
        "blocking": True,
        "reason": None,
        "candidates_found": 0,
        "subfolder_check": None,
    }

    try:
        try:
            token_data = get_token(db, "drive")
        except Exception as exc:
            token_data = None
            result["reason"] = f"drive_token_error: {exc}"
        if not token_data:
            if not result.get("reason"):
                result["reason"] = "no_drive_oauth_token"
        else:
            stored_id = _get_setting(db, DRIVE_ACTIVE_ROOT_KEY)
            stored_source = _get_setting(db, DRIVE_ROOT_SOURCE_KEY)
            subfolder_json = _get_setting(db, DRIVE_SUBFOLDERS_KEY)
            subfolders = json.loads(subfolder_json) if subfolder_json else None

            if stored_id and is_drive_folder_accessible(token_data, stored_id):
                result.update({
                    "resolution_method": "stored_setting",
                    "folder_id": stored_id,
                    "source": stored_source,
                    "accessible": True,
                    "blocking": False,
                    "candidates_found": 1,
                })
            elif settings.google_drive_folder_id and is_drive_folder_accessible(
                token_data, settings.google_drive_folder_id
            ):
                result.update({
                    "resolution_method": "env_configured",
                    "folder_id": settings.google_drive_folder_id,
                    "source": "configured",
                    "accessible": True,
                    "blocking": False,
                    "candidates_found": 1,
                })
            else:
                roots = _find_app_roots(token_data)
                result["candidates_found"] = len(roots)
                if len(roots) == 1:
                    folder_id = roots[0]["id"]
                    if is_drive_folder_accessible(token_data, folder_id):
                        result.update({
                            "resolution_method": "app_properties_search",
                            "folder_id": folder_id,
                            "source": "app-created",
                            "accessible": True,
                            "blocking": False,
                        })
                    else:
                        result["reason"] = "single_candidate_not_accessible"
                elif len(roots) > 1:
                    result["reason"] = "multiple_aarohan_roots_found_owner_decision_required"
                    result["candidate_ids"] = [r["id"] for r in roots]
                elif stored_id:
                    result["reason"] = "stored_root_inaccessible"
                    result["folder_id"] = stored_id
                else:
                    result["reason"] = "no_valid_drive_root_found"

            if result.get("folder_id") and result.get("accessible"):
                result["subfolder_check"] = _verify_subfolders(
                    token_data, result["folder_id"], subfolders
                )
    finally:
        db.close()
        engine.dispose()

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(json.dumps({"blocking": result["blocking"], "folder_id": result.get("folder_id")}))
    return 1 if result["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
