from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import OAuthToken
from app.services.crypto import decrypt_payload, encrypt_payload

# Backward-compatible scope constants for tests and imports
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

from app.services.google_api import (  # noqa: E402
    DEFAULT_GOOGLE_SCOPES,
    OAUTH_REMEDIATION,
    build_oauth_url,
    disconnect_service,
    exchange_code_for_token,
    fetch_user_email,
    integration_status,
    remediation_for_error,
    save_token,
    save_unified_google_token,
    verify_dedicated_account,
    get_token,
)

__all__ = [
    "DEFAULT_GOOGLE_SCOPES",
    "DRIVE_SCOPES",
    "GMAIL_SCOPES",
    "OAUTH_REMEDIATION",
    "build_oauth_url",
    "disconnect_service",
    "exchange_code_for_token",
    "fetch_user_email",
    "get_token",
    "integration_status",
    "remediation_for_error",
    "save_token",
    "save_unified_google_token",
    "verify_dedicated_account",
]
