"""Local development admin bypass — localhost-only, owner stack only."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserSession
from app.services.auth import hash_password
from app.services.environment import E2E_TEST_EMAIL, is_e2e_database, is_owner_database
from app.services.setup import is_setup_complete, mark_setup_complete


def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if not local:
        return f"***@{domain}"
    if len(local) == 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***@{domain}"


def local_dev_bypass_enabled() -> bool:
    return (
        settings.app_env == "local"
        and settings.local_dev_auth_bypass
        and is_owner_database()
    )


def request_is_localhost(request: Request) -> bool:
    host_header = (request.headers.get("host") or "").split(":")[0].strip().lower()
    if host_header in {"localhost", "127.0.0.1"}:
        return True
    client_host = request.client.host if request.client else ""
    return client_host in {"127.0.0.1", "::1", "localhost"}


def deactivate_stray_e2e_user(db: Session) -> bool:
    if not is_owner_database():
        return False
    e2e = db.query(User).filter(User.email.ilike(E2E_TEST_EMAIL)).one_or_none()
    if not e2e:
        return False
    db.query(UserSession).filter(UserSession.user_id == e2e.id).delete()
    e2e.is_active = False
    db.commit()
    return True


def ensure_configured_owner(db: Session) -> User | None:
    email = (settings.admin_email or "").strip()
    if not email:
        return None
    user = db.query(User).filter(User.email.ilike(email)).one_or_none()
    if user:
        changed = False
        if not user.is_admin:
            user.is_admin = True
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if changed:
            db.commit()
        return user
    password = settings.admin_password or ""
    if len(password) < 12:
        return None
    user = User(
        email=email,
        hashed_password=hash_password(password),
        is_admin=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    if not is_setup_complete(db):
        mark_setup_complete(db)
    return user


def local_bypass_status_payload() -> dict:
    email = (settings.admin_email or "").strip()
    return {
        "enabled": local_dev_bypass_enabled(),
        "auto_login": local_dev_bypass_enabled(),
        "owner_email_hint": mask_email(email) if email else None,
        "app_env": settings.app_env,
    }
