"""Database-backed authentication sessions."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthSession, User

SESSION_COOKIE = "careeros_session"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cookie_secure() -> bool:
    return settings.app_env.lower() in {"production", "staging"}


def create_session(
    db: Session,
    user: User,
    *,
    remember_me: bool = True,
    user_agent: str | None = None,
) -> tuple[str, AuthSession]:
    purge_expired_sessions(db)
    raw = secrets.token_urlsafe(32)
    if remember_me:
        expires_at = datetime.utcnow() + timedelta(days=settings.session_remember_days)
    else:
        expires_at = datetime.utcnow() + timedelta(hours=settings.session_default_hours)

    row = AuthSession(
        user_id=user.id,
        token_hash=_hash_token(raw),
        remember_me=remember_me,
        user_agent=(user_agent or "")[:512] or None,
        created_at=datetime.utcnow(),
        last_used_at=datetime.utcnow(),
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return raw, row


def set_session_cookie(response: Response, raw_token: str, *, remember_me: bool) -> None:
    max_age = settings.session_remember_days * 86400 if remember_me else settings.session_default_hours * 3600
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
        max_age=max_age,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")


def get_session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def resolve_session(db: Session, raw_token: str | None) -> AuthSession | None:
    if not raw_token:
        return None
    row = (
        db.query(AuthSession)
        .filter(
            AuthSession.token_hash == _hash_token(raw_token),
            AuthSession.revoked_at.is_(None),
        )
        .one_or_none()
    )
    if not row:
        return None
    if row.expires_at <= datetime.utcnow():
        row.revoked_at = datetime.utcnow()
        db.add(row)
        db.commit()
        return None
    row.last_used_at = datetime.utcnow()
    if row.remember_me:
        row.expires_at = datetime.utcnow() + timedelta(days=settings.session_remember_days)
    db.add(row)
    db.commit()
    return row


def resolve_user_from_session(db: Session, raw_token: str | None) -> User | None:
    row = resolve_session(db, raw_token)
    if not row:
        return None
    return db.query(User).filter(User.id == row.user_id, User.is_active.is_(True)).one_or_none()


def revoke_session(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    row = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == _hash_token(raw_token))
        .one_or_none()
    )
    if row and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        db.add(row)
        db.commit()


def revoke_all_user_sessions(db: Session, user_id: int) -> None:
    rows = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .all()
    )
    now = datetime.utcnow()
    for row in rows:
        row.revoked_at = now
        db.add(row)
    db.commit()


def purge_expired_sessions(db: Session) -> int:
    now = datetime.utcnow()
    rows = (
        db.query(AuthSession)
        .filter(AuthSession.revoked_at.is_(None), AuthSession.expires_at <= now)
        .all()
    )
    for row in rows:
        row.revoked_at = now
        db.add(row)
    if rows:
        db.commit()
    return len(rows)
