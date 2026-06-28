"""Drive root resolution for drive.file scope (app-created folders only)."""

from __future__ import annotations

from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SystemSetting
from app.services.google_api import (
    APP_DRIVE_ROOT_FOLDER_NAME,
    DRIVE_SUBFOLDERS,
    OAUTH_REMEDIATION,
    _auth_headers,
    ensure_drive_folder_tree,
    get_token,
)

DRIVE_ACTIVE_ROOT_KEY = "drive_active_root_folder_id"
DRIVE_ROOT_SOURCE_KEY = "drive_root_source"
DRIVE_SUBFOLDERS_KEY = "drive_subfolder_ids"

DRIVE_ROOT_INACCESSIBLE_WARNING = (
    "Configured Drive root folder is not accessible with drive.file scope. "
    "Manually created folders are not visible unless the app created them. "
    "Click Create Aarohan Drive Root to provision an app-owned root folder."
)


def _get_setting(db: Session, key: str) -> str | None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).one_or_none()
    return row.value if row else None


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).one_or_none()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        db.add(SystemSetting(key=key, value=value))
    db.commit()


def is_drive_folder_accessible(token_data: dict, folder_id: str) -> bool:
    if token_data.get("fixture"):
        return True
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            f"https://www.googleapis.com/drive/v3/files/{folder_id}",
            headers=_auth_headers(token_data),
            params={"fields": "id,name,mimeType,trashed"},
        )
    if response.status_code != 200:
        return False
    body = response.json()
    return not body.get("trashed", False)


def _find_app_root_folder(token_data: dict) -> str | None:
    query = (
        f"name='{APP_DRIVE_ROOT_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=_auth_headers(token_data),
            params={"q": query, "fields": "files(id,name)", "pageSize": 10},
        )
    if response.status_code != 200:
        return None
    files = response.json().get("files", [])
    return files[0]["id"] if files else None


def _create_app_root_folder(token_data: dict) -> str:
    existing = _find_app_root_folder(token_data)
    if existing:
        return existing
    metadata = {"name": APP_DRIVE_ROOT_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://www.googleapis.com/drive/v3/files",
            headers={**_auth_headers(token_data), "Content-Type": "application/json"},
            json=metadata,
        )
    if response.status_code not in (200, 201):
        raise ValueError(response.text)
    return response.json()["id"]


def resolve_active_drive_root(db: Session) -> tuple[str | None, str | None, bool]:
    """Return (folder_id, source, accessible). source is configured|app-created."""
    token_data = get_token(db, "drive")
    if not token_data:
        return None, None, False

    stored_id = _get_setting(db, DRIVE_ACTIVE_ROOT_KEY)
    stored_source = _get_setting(db, DRIVE_ROOT_SOURCE_KEY)
    if stored_id and is_drive_folder_accessible(token_data, stored_id):
        return stored_id, stored_source or "app-created", True

    configured_id = settings.google_drive_folder_id
    if configured_id and is_drive_folder_accessible(token_data, configured_id):
        _set_setting(db, DRIVE_ACTIVE_ROOT_KEY, configured_id)
        _set_setting(db, DRIVE_ROOT_SOURCE_KEY, "configured")
        return configured_id, "configured", True

    if stored_id:
        return stored_id, stored_source, False
    if configured_id:
        return configured_id, "configured", False
    return None, None, False


def set_active_drive_root(db: Session, folder_id: str, source: str) -> None:
    _set_setting(db, DRIVE_ACTIVE_ROOT_KEY, folder_id)
    _set_setting(db, DRIVE_ROOT_SOURCE_KEY, source)


def get_drive_root_status(db: Session) -> dict:
    token_data = get_token(db, "drive")
    configured_id = settings.google_drive_folder_id or None
    active_id, source, accessible = resolve_active_drive_root(db)
    subfolders_raw = _get_setting(db, DRIVE_SUBFOLDERS_KEY)
    subfolders = None
    if subfolders_raw:
        import json

        try:
            subfolders = json.loads(subfolders_raw)
        except json.JSONDecodeError:
            subfolders = None

    warning = None
    if token_data and not token_data.get("fixture"):
        if configured_id and not accessible and active_id == configured_id:
            warning = DRIVE_ROOT_INACCESSIBLE_WARNING
        elif not active_id:
            warning = "No Drive root folder is active. Create an app-owned root folder to enable Drive sync."

    return {
        "configured_folder_id": configured_id,
        "active_folder_id": active_id,
        "source": source,
        "accessible": accessible,
        "warning": warning,
        "subfolders": subfolders,
        "app_root_folder_name": APP_DRIVE_ROOT_FOLDER_NAME,
    }


def try_sync_drive_after_oauth(db: Session) -> dict:
    """Best-effort subfolder sync after OAuth; never raises for inaccessible configured root."""
    token_data = get_token(db, "drive")
    if not token_data:
        return {"ok": False, "warning": "Drive token missing", "folders": {}}

    active_id, source, accessible = resolve_active_drive_root(db)
    if not accessible or not active_id:
        return {
            "ok": True,
            "warning": DRIVE_ROOT_INACCESSIBLE_WARNING,
            "folders": {},
            "drive_root": get_drive_root_status(db),
        }

    folders = ensure_drive_folder_tree(db, root_folder_id=active_id)
    import json

    _set_setting(db, DRIVE_SUBFOLDERS_KEY, json.dumps({k: v for k, v in folders.items() if k != "root"}))
    return {
        "ok": True,
        "warning": None,
        "folders": folders,
        "drive_root": get_drive_root_status(db),
    }


def create_app_drive_root(db: Session) -> dict:
    token_data = get_token(db, "drive")
    if not token_data:
        raise ValueError("Google Drive is not connected")
    if token_data.get("fixture"):
        folders = {name: f"fixture-{name}" for name in DRIVE_SUBFOLDERS}
        folders["root"] = "fixture-aarohan-careeros"
        set_active_drive_root(db, folders["root"], "app-created")
        import json

        _set_setting(db, DRIVE_SUBFOLDERS_KEY, json.dumps({k: v for k, v in folders.items() if k != "root"}))
        return {"root_folder_id": folders["root"], "source": "app-created", "folders": folders}

    root_id = _create_app_root_folder(token_data)
    set_active_drive_root(db, root_id, "app-created")
    folders = ensure_drive_folder_tree(db, root_folder_id=root_id)
    import json

    _set_setting(db, DRIVE_SUBFOLDERS_KEY, json.dumps({k: v for k, v in folders.items() if k != "root"}))
    status = get_drive_root_status(db)
    return {
        "root_folder_id": root_id,
        "source": "app-created",
        "folders": folders,
        "drive_root": status,
    }


def sync_drive_subfolders(db: Session) -> dict[str, str]:
    active_id, _, accessible = resolve_active_drive_root(db)
    if not accessible or not active_id:
        raise ValueError(DRIVE_ROOT_INACCESSIBLE_WARNING)
    folders = ensure_drive_folder_tree(db, root_folder_id=active_id)
    import json

    _set_setting(db, DRIVE_SUBFOLDERS_KEY, json.dumps({k: v for k, v in folders.items() if k != "root"}))
    return folders
