"""Google OAuth helpers and REST API clients (httpx-based, no google-auth dependency)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta
from email.utils import parseaddr
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import OAuthToken, ProcessedGmailMessage
from app.services.crypto import decrypt_payload, encrypt_payload

DEFAULT_GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.readonly",
]

OPTIONAL_GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"

DEFAULT_GMAIL_LABELS = [
    "Aarohan/Job Alerts/LinkedIn",
    "Aarohan/Job Alerts/Indeed",
    "Aarohan/Job Alerts/Dice",
    "Aarohan/Job Alerts/Glassdoor",
    "Aarohan/Job Alerts/USAJOBS",
    "Aarohan/Applications",
    "Aarohan/Interviews",
    "Aarohan/Recruiters",
    "Aarohan/Rejections",
    "Aarohan/Offers",
    "Aarohan/Processing",
]

DRIVE_SUBFOLDERS = [
    "01_Career_Vault",
    "02_Application_Packets",
    "03_Interview_Preparation",
    "04_Consulting",
    "05_Reports",
    "99_Archive",
]

APP_DRIVE_ROOT_FOLDER_NAME = "aarohan-careeros"

OAUTH_REMEDIATION: dict[str, str] = {
    "invalid_client": "OAuth client secret or client ID is invalid. Verify C:\\AarohanSecrets\\google-oauth-client.json.",
    "redirect_uri_mismatch": (
        "Redirect URI mismatch. Add http://localhost:8000/api/integrations/google/callback "
        "and http://127.0.0.1:8000/api/integrations/google/callback in Google Cloud Console."
    ),
    "invalid_grant": "Refresh token revoked or expired. Disconnect Google and reconnect with consent.",
    "access_denied": "OAuth consent was denied. Retry Connect Google and approve all requested scopes.",
    "insufficient_scope": "Missing required scope. Disconnect and reconnect Google integration.",
    "folder_not_found": "Drive root folder is inaccessible. Verify GOOGLE_DRIVE_ROOT_FOLDER_ID and sharing.",
    "wrong_account": (
        f"Connected account must be {settings.career_gmail_address or 'swapnilpatil.tech@gmail.com'}. "
        "Disconnect and reconnect with the dedicated career Gmail."
    ),
    "api_disabled": "Gmail or Drive API is disabled in Google Cloud project aarohan-careeros-500722.",
    "oauth_not_configured": "Google OAuth is not configured. Place client JSON at C:\\AarohanSecrets\\google-oauth-client.json.",
}


def remediation_for_error(error: str, *, default: str = "Google integration error") -> str:
    lowered = error.lower()
    for key, message in OAUTH_REMEDIATION.items():
        if key in lowered:
            return message
    if "403" in lowered and "gmail" in lowered:
        return OAUTH_REMEDIATION["api_disabled"]
    if "404" in lowered and "folder" in lowered:
        return OAUTH_REMEDIATION["folder_not_found"]
    return default


def integration_status(db: Session) -> dict:
    from app.services.drive_settings import get_drive_root_status
    from app.services.google_health import evaluate_google_health

    health = evaluate_google_health(db)
    drive_root: dict = {
        "configured_folder_id": settings.google_drive_folder_id or None,
        "active_folder_id": None,
        "source": None,
        "accessible": health.get("drive_accessible", False),
        "warning": None,
        "subfolders": None,
        "app_root_folder_name": APP_DRIVE_ROOT_FOLDER_NAME,
    }
    if health.get("connected") and not settings.oauth_fixture_mode:
        drive_root = get_drive_root_status(db)

    google_connected = health["state"] not in {"DISCONNECTED"}
    return {
        "google": {"connected": google_connected, "account_email": health.get("account_email")},
        "gmail": {"connected": google_connected, "account_email": health.get("account_email")},
        "drive": {"connected": google_connected, "account_email": health.get("account_email")},
        "google_connected": google_connected,
        "google_health_state": health["state"],
        "google_display_status": health["display_status"],
        "token_usable": health.get("token_usable", False),
        "connected_account": health.get("account_email"),
        "google_remediation": health.get("remediation"),
        "google_health": health,
        "fixture_mode": settings.oauth_fixture_mode,
        "oauth_configured": bool(settings.google_client_id and settings.google_client_secret),
        "scheduling_enabled": settings.scheduling_enabled,
        "external_email_send_enabled": settings.enable_external_email_send,
        "dedicated_gmail": settings.career_gmail_address or "swapnilpatil.tech@gmail.com",
        "drive_root_folder_id": drive_root.get("active_folder_id") or settings.google_drive_folder_id,
        "drive_root": drive_root,
    }


def _expires_at(token_data: dict) -> datetime | None:
    if token_data.get("expiry"):
        return token_data["expiry"]
    if token_data.get("expires_in"):
        return datetime.utcnow() + timedelta(seconds=int(token_data["expires_in"]))
    return None


def save_token(
    db: Session,
    *,
    service: str,
    token_data: dict,
    account_email: str | None = None,
    scopes: list[str] | None = None,
) -> OAuthToken:
    existing_rows = (
        db.query(OAuthToken)
        .filter(OAuthToken.provider == "google", OAuthToken.service == service, OAuthToken.is_active.is_(True))
        .all()
    )
    preserved_refresh: str | None = None
    for row in existing_rows:
        try:
            prior = decrypt_payload(row.encrypted_token)
            if prior.get("refresh_token"):
                preserved_refresh = prior["refresh_token"]
        except Exception:
            pass
        row.is_active = False
    if preserved_refresh and not token_data.get("refresh_token"):
        token_data = {**token_data, "refresh_token": preserved_refresh}
    if scopes:
        token_data = {**token_data, "scopes": scopes}
    row = OAuthToken(
        provider="google",
        service=service,
        account_email=account_email,
        encrypted_token=encrypt_payload(token_data),
        scopes=",".join(token_data.get("scopes", scopes or [])),
        expires_at=_expires_at(token_data),
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_unified_google_token(db: Session, token_data: dict, account_email: str, scopes: list[str]) -> None:
    for service in ("google", "gmail", "drive"):
        save_token(db, service=service, token_data=token_data, account_email=account_email, scopes=scopes)


def _refresh_access_token(db: Session, row: OAuthToken, token_data: dict) -> dict:
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise ValueError(remediation_for_error("invalid_grant"))
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code != 200:
        raise ValueError(remediation_for_error(response.text))
    refreshed = {**token_data, **response.json()}
    if "refresh_token" not in refreshed:
        refreshed["refresh_token"] = refresh_token
    row.encrypted_token = encrypt_payload(refreshed)
    row.expires_at = _expires_at(refreshed)
    db.add(row)
    db.commit()
    return refreshed


def get_token(db: Session, service: str = "google") -> dict | None:
    if settings.oauth_fixture_mode:
        return {"access_token": "fixture-token", "token_type": "Bearer", "fixture": True}
    for candidate in (service, "google", "gmail", "drive"):
        row = (
            db.query(OAuthToken)
            .filter(
                OAuthToken.provider == "google",
                OAuthToken.service == candidate,
                OAuthToken.is_active.is_(True),
            )
            .order_by(OAuthToken.connected_at.desc())
            .first()
        )
        if row:
            try:
                token_data = decrypt_payload(row.encrypted_token)
            except Exception:
                continue
            if row.expires_at and row.expires_at <= datetime.utcnow() + timedelta(seconds=60):
                token_data = _refresh_access_token(db, row, token_data)
            return token_data
    return None


def disconnect_service(db: Session, service: str) -> bool:
    services = ["google", "gmail", "drive"] if service in {"google", "gmail", "drive", "all"} else [service]
    rows = (
        db.query(OAuthToken)
        .filter(
            OAuthToken.provider == "google",
            OAuthToken.service.in_(services),
            OAuthToken.is_active.is_(True),
        )
        .all()
    )
    if not rows:
        return False
    token_data = None
    for row in rows:
        if not token_data:
            try:
                token_data = decrypt_payload(row.encrypted_token)
            except Exception:
                token_data = None
        row.is_active = False
    db.commit()
    if token_data and token_data.get("access_token") and not settings.oauth_fixture_mode:
        try:
            with httpx.Client(timeout=15.0) as client:
                client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": token_data.get("access_token")},
                )
        except Exception:
            pass
    return True


def build_oauth_url(state: str, *, extra_scopes: list[str] | None = None, prompt_consent: bool = False) -> str:
    if not settings.google_client_id:
        raise ValueError(OAUTH_REMEDIATION["oauth_not_configured"])
    scopes = list(DEFAULT_GOOGLE_SCOPES)
    if extra_scopes:
        scopes.extend(extra_scopes)
    scope_param = "+".join(scopes)
    redirect = settings.google_oauth_redirect_uri
    prompt = "consent" if prompt_consent else "select_account"
    return (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.google_client_id}&"
        f"redirect_uri={redirect}&"
        "response_type=code&"
        f"scope={scope_param}&"
        "access_type=offline&"
        "include_granted_scopes=true&"
        f"prompt={prompt}&"
        f"state={state}"
    )


def exchange_code_for_token(code: str) -> dict:
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValueError(OAUTH_REMEDIATION["oauth_not_configured"])
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code != 200:
        raise ValueError(remediation_for_error(response.text))
    return response.json()


def fetch_user_email(access_token: str) -> str:
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code != 200:
        raise ValueError(remediation_for_error(response.text, default="Unable to verify Google account identity."))
    return response.json().get("email", "")


def verify_dedicated_account(email: str) -> None:
    expected = (settings.career_gmail_address or "swapnilpatil.tech@gmail.com").lower()
    if email.lower() != expected:
        raise ValueError(OAUTH_REMEDIATION["wrong_account"])


def _auth_headers(token_data: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_data['access_token']}"}


def _decode_gmail_body(payload: dict) -> str:
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"] + "==").decode("utf-8", errors="replace")
    parts = payload.get("parts") or []
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"] + "==").decode("utf-8", errors="replace")
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/html" and part.get("body", {}).get("data"):
            from app.services.sanitize import sanitize_html

            html = base64.urlsafe_b64decode(part["body"]["data"] + "==").decode("utf-8", errors="replace")
            return sanitize_html(html)
    for part in parts:
        text = _decode_gmail_body(part)
        if text:
            return text
    return ""


def list_gmail_labels(token_data: dict) -> dict[str, str]:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/labels",
            headers=_auth_headers(token_data),
        )
    if response.status_code != 200:
        raise ValueError(remediation_for_error(response.text))
    return {label["name"]: label["id"] for label in response.json().get("labels", [])}


def resolve_aarohan_label_ids(token_data: dict) -> dict[str, str]:
    labels = list_gmail_labels(token_data)
    resolved: dict[str, str] = {}
    for name in DEFAULT_GMAIL_LABELS:
        if name in labels:
            resolved[name] = labels[name]
    return resolved


def fetch_gmail_messages(
    db: Session,
    *,
    query: str = "",
    label_ids: list[str] | None = None,
    max_results: int = 50,
) -> list[dict]:
    token_data = get_token(db, "gmail")
    if not token_data:
        return []
    if token_data.get("fixture"):
        from app.integrations.google import FixtureGmailClient

        return FixtureGmailClient().fetch_recent_messages(query=query, max_results=max_results)

    messages: list[dict] = []
    page_token: str | None = None
    fetched = 0
    params_base: dict[str, Any] = {"maxResults": min(max_results, 100)}
    if query:
        params_base["q"] = query
    if label_ids:
        params_base["labelIds"] = label_ids

    while fetched < max_results:
        params = dict(params_base)
        params["maxResults"] = min(max_results - fetched, 100)
        if page_token:
            params["pageToken"] = page_token
        with httpx.Client(timeout=30.0) as client:
            list_resp = client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=_auth_headers(token_data),
                params=params,
            )
        if list_resp.status_code != 200:
            raise ValueError(remediation_for_error(list_resp.text))
        body = list_resp.json()
        for item in body.get("messages", []):
            if fetched >= max_results:
                break
            message_id = item["id"]
            if db.query(ProcessedGmailMessage).filter(ProcessedGmailMessage.message_id == message_id).first():
                continue
            with httpx.Client(timeout=30.0) as client:
                detail = client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                    headers=_auth_headers(token_data),
                    params={"format": "full"},
                )
            if detail.status_code != 200:
                continue
            payload = detail.json()
            headers = {h["name"].lower(): h["value"] for h in payload.get("payload", {}).get("headers", [])}
            sender = parseaddr(headers.get("from", ""))[1] or headers.get("from", "")
            subject = headers.get("subject", "")
            body_text = _decode_gmail_body(payload.get("payload", {}))
            messages.append(
                {
                    "id": message_id,
                    "thread_id": payload.get("threadId"),
                    "sender": sender,
                    "subject": subject,
                    "body_text": body_text,
                }
            )
            fetched += 1
        page_token = body.get("nextPageToken")
        if not page_token:
            break
    return messages


def fetch_aarohan_labeled_messages(db: Session, *, max_results: int = 50) -> list[dict]:
    token_data = get_token(db, "gmail")
    if not token_data or token_data.get("fixture"):
        return fetch_gmail_messages(db, query="label:Aarohan", max_results=max_results)
    label_map = resolve_aarohan_label_ids(token_data)
    if not label_map:
        return fetch_gmail_messages(db, query="label:Aarohan", max_results=max_results)
    all_messages: list[dict] = []
    seen: set[str] = set()
    for label_name, label_id in label_map.items():
        batch = fetch_gmail_messages(db, label_ids=[label_id], max_results=max_results)
        for msg in batch:
            if msg["id"] in seen:
                continue
            seen.add(msg["id"])
            msg["label"] = label_name
            all_messages.append(msg)
    return all_messages[:max_results]


def mark_gmail_message_processed(db: Session, message_id: str) -> None:
    if db.query(ProcessedGmailMessage).filter(ProcessedGmailMessage.message_id == message_id).first():
        return
    db.add(ProcessedGmailMessage(message_id=message_id))
    db.commit()


def ensure_drive_folder_tree(db: Session, root_folder_id: str | None = None) -> dict[str, str]:
    token_data = get_token(db, "drive")
    if not token_data:
        raise ValueError("Google Drive is not connected")
    if token_data.get("fixture"):
        return {name: f"fixture-{name}" for name in DRIVE_SUBFOLDERS}

    root_id = root_folder_id
    if not root_id:
        from app.services.drive_settings import resolve_active_drive_root

        root_id, _, accessible = resolve_active_drive_root(db)
        if not root_id or not accessible:
            raise ValueError(OAUTH_REMEDIATION["folder_not_found"])

    folder_map: dict[str, str] = {"root": root_id}
    with httpx.Client(timeout=30.0) as client:
        root_check = client.get(
            f"https://www.googleapis.com/drive/v3/files/{root_id}",
            headers=_auth_headers(token_data),
            params={"fields": "id,name,mimeType"},
        )
    if root_check.status_code != 200:
        raise ValueError(OAUTH_REMEDIATION["folder_not_found"])

    for name in DRIVE_SUBFOLDERS:
        query = (
            f"name='{name}' and '{root_id}' in parents and mimeType='application/vnd.google-apps.folder' "
            "and trashed=false"
        )
        with httpx.Client(timeout=30.0) as client:
            search = client.get(
                "https://www.googleapis.com/drive/v3/files",
                headers=_auth_headers(token_data),
                params={"q": query, "fields": "files(id,name)", "pageSize": 1},
            )
        if search.status_code != 200:
            raise ValueError(remediation_for_error(search.text))
        files = search.json().get("files", [])
        if files:
            folder_map[name] = files[0]["id"]
            continue
        metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [root_id]}
        with httpx.Client(timeout=30.0) as client:
            created = client.post(
                "https://www.googleapis.com/drive/v3/files",
                headers={**_auth_headers(token_data), "Content-Type": "application/json"},
                json=metadata,
            )
        if created.status_code not in (200, 201):
            raise ValueError(remediation_for_error(created.text))
        folder_map[name] = created.json()["id"]
    return folder_map


def upload_file_to_drive(
    db: Session,
    local_path: str,
    filename: str,
    folder_id: str | None = None,
) -> dict:
    token_data = get_token(db, "drive")
    if not token_data:
        raise ValueError("Google Drive is not connected")
    if token_data.get("fixture"):
        return {
            "file_id": f"fixture-{filename}",
            "web_view_link": f"fixture-drive://{folder_id or settings.google_drive_folder_id}/{filename}",
        }

    target_folder = folder_id
    if not target_folder:
        from app.services.drive_settings import resolve_active_drive_root

        active_id, _, accessible = resolve_active_drive_root(db)
        target_folder = active_id if accessible else settings.google_drive_folder_id
    path = Path(local_path)
    metadata = {"name": filename, "parents": [target_folder]} if target_folder else {"name": filename}
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            headers=_auth_headers(token_data),
            files={
                "metadata": ("metadata", json.dumps(metadata), "application/json"),
                "file": (filename, path.read_bytes()),
            },
        )
    if response.status_code not in (200, 201):
        raise ValueError(remediation_for_error(response.text))
    body = response.json()
    return {
        "file_id": body.get("id"),
        "web_view_link": f"https://drive.google.com/file/d/{body.get('id')}/view",
        "md5_checksum": body.get("md5Checksum"),
        "version": body.get("version"),
    }


def generate_test_eml(*, to: str, subject: str, body: str) -> str:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = settings.career_gmail_address or "swapnilpatil.tech@gmail.com"
    msg["Subject"] = subject if subject.startswith("[AAROHAN TEST]") else f"[AAROHAN TEST] {subject}"
    msg.set_content(body)
    return msg.as_string()
