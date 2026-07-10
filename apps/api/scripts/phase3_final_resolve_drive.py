#!/usr/bin/env python3
"""Final Drive root resolution with bind and restart persistence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import SystemSetting
from app.services.drive_settings import (
    DRIVE_ACTIVE_ROOT_KEY,
    DRIVE_ROOT_SOURCE_KEY,
    DRIVE_SUBFOLDERS,
    DRIVE_SUBFOLDERS_KEY,
    ensure_drive_folder_tree,
    get_drive_root_status,
    is_drive_folder_accessible,
    resolve_active_drive_root,
    set_active_drive_root,
)
from app.services.google_api import APP_DRIVE_ROOT_FOLDER_NAME, _auth_headers, get_token
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
                "fields": "files(id,name,appProperties,owners,createdTime,ownedByMe)",
                "pageSize": 20,
            },
        )
    if resp.status_code != 200:
        return []
    files = resp.json().get("files", [])
    return [f for f in files if f.get("ownedByMe", True)]


def _restart_candidate_api() -> bool:
    subprocess.run(["docker", "restart", "aarohan-candidate-api"], capture_output=True, timeout=120, check=False)
    for _ in range(30):
        try:
            if httpx.get("http://127.0.0.1:8002/health", timeout=5.0).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Final Drive root resolution")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--bind", action="store_true", default=True)
    args = parser.parse_args(argv)

    if not args.database_url or settings.oauth_fixture_mode:
        return 1

    validate_recovery_database_identity(database_url=args.database_url)
    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    result: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "resolution_method": None,
        "folder_id": None,
        "accessible": False,
        "blocking": True,
        "reason": None,
        "candidates_found": 0,
        "subfolder_check": None,
        "restart_persistence": None,
    }

    try:
        token_data = get_token(db, "drive")
        if not token_data:
            result["reason"] = "no_drive_oauth_token"
        else:
            stored_id = _get_setting(db, DRIVE_ACTIVE_ROOT_KEY)
            stored_source = _get_setting(db, DRIVE_ROOT_SOURCE_KEY)
            configured_id = settings.google_drive_folder_id

            chosen_id = None
            chosen_source = None
            method = None

            if stored_id and is_drive_folder_accessible(token_data, stored_id):
                chosen_id, chosen_source, method = stored_id, stored_source or "stored", "stored_setting"
            elif configured_id and is_drive_folder_accessible(token_data, configured_id):
                chosen_id, chosen_source, method = configured_id, "configured", "env_configured"
            else:
                roots = _find_app_roots(token_data)
                result["candidates_found"] = len(roots)
                if len(roots) == 1:
                    chosen_id = roots[0]["id"]
                    props = roots[0].get("appProperties") or {}
                    if props.get("aarohan") or props.get("app") == "careeros":
                        method = "app_properties_search"
                    else:
                        method = "single_owned_root_by_rules"
                    chosen_source = "app-created"
                elif len(roots) > 1:
                    result["reason"] = "multiple_aarohan_roots_found_owner_decision_required"
                    result["candidate_ids"] = [r["id"] for r in roots]
                elif stored_id:
                    result["reason"] = "stored_root_inaccessible"
                    result["folder_id"] = stored_id
                elif configured_id:
                    result["reason"] = "configured_root_inaccessible"
                else:
                    result["reason"] = "no_valid_drive_root_found"

            if chosen_id and args.bind:
                set_active_drive_root(db, chosen_id, chosen_source or "app-created")
                folders = ensure_drive_folder_tree(db, root_folder_id=chosen_id)
                db.query(SystemSetting).filter(SystemSetting.key == DRIVE_SUBFOLDERS_KEY).delete()
                db.add(SystemSetting(key=DRIVE_SUBFOLDERS_KEY, value=json.dumps(
                    {k: v for k, v in folders.items() if k != "root"}
                )))
                db.commit()

            if chosen_id:
                accessible = is_drive_folder_accessible(token_data, chosen_id)
                subfolder_map = json.loads(_get_setting(db, DRIVE_SUBFOLDERS_KEY) or "{}")
                present = []
                missing = []
                for name in DRIVE_SUBFOLDERS:
                    fid = subfolder_map.get(name)
                    if fid and is_drive_folder_accessible(token_data, fid):
                        present.append(name)
                    else:
                        missing.append(name)
                result.update({
                    "resolution_method": method,
                    "folder_id": chosen_id,
                    "source": chosen_source,
                    "accessible": accessible,
                    "blocking": not accessible,
                    "subfolder_check": {
                        "present": present,
                        "missing": missing,
                        "complete": not missing,
                    },
                })
                if accessible:
                    result["blocking"] = False
                    result["reason"] = None

            if not result.get("blocking") and result.get("folder_id"):
                before = get_drive_root_status(db)
                restarted = _restart_candidate_api()
                after = get_drive_root_status(db)
                result["restart_persistence"] = {
                    "restarted": restarted,
                    "folder_id_before": before.get("active_folder_id"),
                    "folder_id_after": after.get("active_folder_id"),
                    "accessible_after": after.get("accessible"),
                    "passed": (
                        restarted
                        and before.get("active_folder_id") == after.get("active_folder_id")
                        and after.get("accessible")
                    ),
                }
                if not result["restart_persistence"]["passed"]:
                    result["blocking"] = True
                    result["reason"] = "drive_root_not_persistent_after_restart"
    except Exception as exc:
        result["reason"] = str(exc)[:240]
        result["blocking"] = True
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
