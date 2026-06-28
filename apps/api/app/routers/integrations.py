import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services.audit import write_audit
from app.services.google_api import (
    DEFAULT_GOOGLE_SCOPES,
    OPTIONAL_GMAIL_SEND_SCOPE,
    build_oauth_url,
    disconnect_service,
    exchange_code_for_token,
    fetch_gmail_messages,
    fetch_user_email,
    generate_test_eml,
    integration_status,
    mark_gmail_message_processed,
    remediation_for_error,
    save_unified_google_token,
    verify_dedicated_account,
)
from app.services.integrations import get_gmail_client, sync_drive_folders

router = APIRouter(prefix="/integrations", tags=["integrations"])
_oauth_states: dict[str, dict[str, str | bool]] = {}


@router.get("/status")
def status(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    return integration_status(db)


@router.get("/google/connect")
def connect_google(
    service: str = Query("google", pattern="^(google|gmail|drive)$"),
    enable_test_email: bool = False,
    _: User = Depends(get_current_user),
) -> dict:
    if not settings.google_client_id or not settings.google_client_secret:
        return {
            "configured": False,
            "message": remediation_for_error("oauth_not_configured"),
        }
    state = secrets.token_urlsafe(16)
    extra = [OPTIONAL_GMAIL_SEND_SCOPE] if enable_test_email and settings.enable_external_email_send else None
    _oauth_states[state] = {"service": service, "enable_test_email": enable_test_email}
    try:
        auth_url = build_oauth_url(state, extra_scopes=extra)
    except ValueError as exc:
        return {"configured": False, "message": str(exc)}
    return {"auth_url": auth_url, "service": service, "scopes": DEFAULT_GOOGLE_SCOPES}


@router.get("/google/callback")
def google_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    state_meta = _oauth_states.pop(state, None)
    if not state_meta:
        detail = remediation_for_error("invalid_grant", default="Invalid OAuth state. Retry Connect Google.")
        raise HTTPException(status_code=400, detail=detail)
    try:
        token_data = exchange_code_for_token(code)
        email = fetch_user_email(token_data["access_token"])
        verify_dedicated_account(email)
        scopes = list(DEFAULT_GOOGLE_SCOPES)
        if state_meta.get("enable_test_email"):
            scopes.append(OPTIONAL_GMAIL_SEND_SCOPE)
        save_unified_google_token(db, token_data, email, scopes)
        write_audit(db, event_type="oauth.connected", actor=email, resource_type="oauth", resource_id="google")
        folders = sync_drive_folders(db)
        body = (
            "<html><body style='font-family:Arial;padding:24px'>"
            "<h2>Google connected</h2>"
            f"<p>Account: {email}</p>"
            f"<p>Drive folders ready: {len(folders)}</p>"
            "<p>You may close this tab and return to Settings.</p>"
            "</body></html>"
        )
        return HTMLResponse(content=body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=remediation_for_error(str(exc))) from exc


@router.post("/google/disconnect")
def google_disconnect(
    service: str = "all",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ok = disconnect_service(db, service)
    if ok:
        write_audit(
            db,
            event_type="oauth.disconnected",
            actor=current_user.email,
            resource_type="oauth",
            resource_id=service,
        )
    return {"disconnected": ok, "service": service}


@router.post("/google/refresh")
def google_refresh(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    from app.services.oauth import get_token

    try:
        token = get_token(db, "google")
        if not token:
            raise ValueError("Google is not connected")
        return {"refreshed": True, "has_token": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/google/drive/folders")
def drive_folders(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    try:
        folders = sync_drive_folders(db)
        return {"folders": folders}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/gmail/sync")
def sync_gmail(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    from app.services.auth import process_recruiter_signal

    messages = client.fetch_recent_messages()
    created = []
    for msg in messages:
        signal = process_recruiter_signal(
            db,
            {
                "source": "gmail",
                "sender": msg.get("sender"),
                "subject": msg.get("subject"),
                "body_text": msg.get("body_text", ""),
            },
        )
        if msg.get("id"):
            mark_gmail_message_processed(db, msg["id"])
        created.append({"id": signal.id, "signal_type": signal.signal_type})
    write_audit(
        db,
        event_type="gmail.synced",
        actor=current_user.email,
        resource_type="gmail",
        resource_id="sync",
        details={"processed": len(created)},
    )
    return {"processed": len(created), "signals": created}


@router.post("/gmail/sync-fixture")
def sync_fixture_gmail(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    from app.integrations.google import FixtureGmailClient
    from app.services.auth import process_recruiter_signal

    messages = FixtureGmailClient().fetch_recent_messages()
    created = []
    for msg in messages:
        signal = process_recruiter_signal(
            db,
            {
                "source": "gmail_fixture",
                "sender": msg.get("sender"),
                "subject": msg.get("subject"),
                "body_text": msg.get("body_text", ""),
            },
        )
        created.append({"id": signal.id, "signal_type": signal.signal_type})
    return {"processed": len(created), "signals": created}


@router.post("/gmail/test-send")
def gmail_test_send(
    to: str,
    subject: str,
    body: str,
    confirm: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not settings.enable_external_email_send:
        eml = generate_test_eml(to=to, subject=subject, body=body)
        out_dir = Path(settings.generated_root) / "test_email"
        out_dir.mkdir(parents=True, exist_ok=True)
        eml_path = out_dir / f"test_{secrets.token_hex(4)}.eml"
        eml_path.write_text(eml, encoding="utf-8")
        return {
            "mode": "eml",
            "path": str(eml_path),
            "message": "External send disabled; generated .eml draft instead.",
        }
    allowlist = {item.strip().lower() for item in settings.test_email_allowlist.split(",") if item.strip()}
    if to.lower() not in allowlist:
        raise HTTPException(status_code=400, detail="Recipient not in TEST_EMAIL_ALLOWLIST")
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required for test send")
    raise HTTPException(
        status_code=501,
        detail="Gmail send requires incremental OAuth consent via Connect with Enable Test Email.",
    )
