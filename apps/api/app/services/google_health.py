"""Canonical Google integration health state machine."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import OAuthToken
from app.services.crypto import decrypt_payload
from app.services.drive_settings import resolve_active_drive_root
from app.services.google_api import DEFAULT_GOOGLE_SCOPES, get_token, remediation_for_error

STATES = (
    "DISCONNECTED",
    "LINKED_UNVERIFIED",
    "HEALTHY",
    "DEGRADED",
    "REAUTH_REQUIRED",
)


def _active_google_row(db: Session) -> OAuthToken | None:
    return (
        db.query(OAuthToken)
        .filter(
            OAuthToken.provider == "google",
            OAuthToken.service == "google",
            OAuthToken.is_active.is_(True),
        )
        .order_by(OAuthToken.id.desc())
        .first()
    )


def _scope_status(scopes_csv: str | None) -> dict:
    granted = {s.strip() for s in (scopes_csv or "").split(",") if s.strip()}
    required = set(DEFAULT_GOOGLE_SCOPES)
    missing = sorted(required - granted)
    return {
        "required_count": len(required),
        "granted_count": len(granted & required),
        "missing_scopes": missing,
        "scopes_ok": not missing,
    }


def evaluate_google_health(db: Session) -> dict:
    if settings.oauth_fixture_mode:
        return {
            "state": "DISCONNECTED",
            "display_status": "Fixture mode",
            "connected": False,
            "token_usable": False,
            "account_email": None,
            "remediation": "Owner stack requires OAUTH_FIXTURE_MODE=false for live Google.",
            "scope_status": _scope_status(None),
            "last_successful_refresh": None,
            "last_drive_check_ok": False,
            "last_gmail_check_ok": False,
            "drive_accessible": False,
            "fixture_mode": True,
        }

    row = _active_google_row(db)
    if not row:
        return {
            "state": "DISCONNECTED",
            "display_status": "Not connected",
            "connected": False,
            "token_usable": False,
            "account_email": None,
            "remediation": "Use Settings → Connect Google with the dedicated career Gmail account.",
            "scope_status": _scope_status(None),
            "last_successful_refresh": None,
            "last_drive_check_ok": False,
            "last_gmail_check_ok": False,
            "drive_accessible": False,
            "fixture_mode": False,
        }

    account = row.account_email
    scope_status = _scope_status(row.scopes)
    token_data = None
    decrypt_error = None
    try:
        token_data = decrypt_payload(row.encrypted_token)
    except Exception as exc:
        decrypt_error = str(exc)

    if decrypt_error:
        return {
            "state": "REAUTH_REQUIRED",
            "display_status": "Re-authentication required",
            "connected": True,
            "token_usable": False,
            "account_email": account,
            "remediation": (
                "Stored tokens cannot be decrypted — TOKEN_ENCRYPTION_KEY may have changed. "
                "Reconnect Google once to migrate tokens."
            ),
            "scope_status": scope_status,
            "last_successful_refresh": None,
            "last_drive_check_ok": False,
            "last_gmail_check_ok": False,
            "drive_accessible": False,
            "fixture_mode": False,
        }

    refresh_ok = False
    refresh_error = None
    last_refresh = None
    try:
        live = get_token(db, "google")
        refresh_ok = bool(live and live.get("access_token"))
        last_refresh = datetime.utcnow().isoformat() + "Z"
    except Exception as exc:
        refresh_error = str(exc)
        msg = remediation_for_error(refresh_error)
        permanent = any(
            token in refresh_error.lower()
            for token in ("invalid_grant", "invalid_client", "insufficient_scope", "unauthorized_client")
        )
        return {
            "state": "REAUTH_REQUIRED" if permanent else "DEGRADED",
            "display_status": "Re-authentication required" if permanent else "Temporarily unavailable",
            "connected": True,
            "token_usable": False,
            "account_email": account,
            "remediation": msg,
            "scope_status": scope_status,
            "last_successful_refresh": None,
            "last_drive_check_ok": False,
            "last_gmail_check_ok": False,
            "drive_accessible": False,
            "fixture_mode": False,
        }

    if not scope_status["scopes_ok"]:
        return {
            "state": "REAUTH_REQUIRED",
            "display_status": "Scope update required",
            "connected": True,
            "token_usable": False,
            "account_email": account,
            "remediation": "Disconnect and reconnect Google to grant all required scopes.",
            "scope_status": scope_status,
            "last_successful_refresh": last_refresh,
            "last_drive_check_ok": False,
            "last_gmail_check_ok": False,
            "drive_accessible": False,
            "fixture_mode": False,
        }

    _, active_root, drive_ok = resolve_active_drive_root(db)
    gmail_ok = refresh_ok
    if refresh_ok and not drive_ok:
        return {
            "state": "DEGRADED",
            "display_status": "Connected — Drive temporarily unavailable",
            "connected": True,
            "token_usable": True,
            "account_email": account,
            "remediation": (
                "Google account is healthy but the Drive root is not accessible. "
                "Do not reconnect — verify the app-owned root in Settings or create one if missing."
            ),
            "scope_status": scope_status,
            "last_successful_refresh": last_refresh,
            "last_drive_check_ok": False,
            "last_gmail_check_ok": gmail_ok,
            "drive_accessible": False,
            "drive_root_configured": bool(active_root),
            "fixture_mode": False,
        }

    if not refresh_ok:
        return {
            "state": "LINKED_UNVERIFIED",
            "display_status": "Linked — verification pending",
            "connected": True,
            "token_usable": False,
            "account_email": account,
            "remediation": "Run local validation or sync Gmail to complete verification.",
            "scope_status": scope_status,
            "last_successful_refresh": None,
            "last_drive_check_ok": drive_ok,
            "last_gmail_check_ok": False,
            "drive_accessible": drive_ok,
            "fixture_mode": False,
        }

    return {
        "state": "HEALTHY",
        "display_status": "Healthy",
        "connected": True,
        "token_usable": True,
        "account_email": account,
        "remediation": None,
        "scope_status": scope_status,
        "last_successful_refresh": last_refresh,
        "last_drive_check_ok": drive_ok,
        "last_gmail_check_ok": gmail_ok,
        "drive_accessible": drive_ok,
        "fixture_mode": False,
    }
