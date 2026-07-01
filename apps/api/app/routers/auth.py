from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_optional_user
from app.models import User
from app.schemas import LoginRequest, TokenResponse
from app.services.auth import hash_password, verify_password
from app.services.career_vault import sync_evidence_registry
from app.services.setup import has_admin_user, is_setup_complete, mark_setup_complete
from app.services.environment import assert_e2e_user_allowed
from app.services.sessions import (
    REMEMBER_ME_DAYS,
    SESSION_COOKIE_NAME,
    SHORT_SESSION_HOURS,
    cleanup_expired_sessions,
    create_session,
    get_user_for_session_token,
    revoke_session_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class SetupRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = True


class LoginBody(BaseModel):
    email: str
    password: str
    remember_me: bool = True


def _cookie_secure() -> bool:
    return settings.app_env not in {"development", "test", "local"}


def _set_session_cookie(response: Response, raw_token: str, *, remember_me: bool) -> None:
    cookie_kwargs: dict = {
        "key": SESSION_COOKIE_NAME,
        "value": raw_token,
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": "lax",
        "path": "/",
    }
    if remember_me:
        cookie_kwargs["max_age"] = REMEMBER_ME_DAYS * 24 * 60 * 60
    # remember_me=False → no max_age: browser-session cookie (closes with browser)
    response.set_cookie(**cookie_kwargs)


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _issue_session(
    response: Response,
    db: Session,
    user: User,
    *,
    remember_me: bool,
    user_agent: str | None,
) -> TokenResponse:
    cleanup_expired_sessions(db)
    raw_token, session = create_session(
        db, user, remember_me=remember_me, user_agent=user_agent
    )
    _set_session_cookie(response, raw_token, remember_me=remember_me)
    expose = settings.expose_session_token_in_login_response or settings.app_env in {"test", "local"}
    return TokenResponse(
        access_token=raw_token if expose else "",
        token_type="session",
        expires_at=session.expires_at.isoformat(),
        remember_me=remember_me,
    )


@router.get("/setup-status")
def setup_status(db: Session = Depends(get_db)) -> dict:
    return {
        "setup_required": not is_setup_complete(db) and not has_admin_user(db),
        "has_admin": has_admin_user(db),
    }


@router.get("/session")
def get_session(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> dict:
    if not current_user:
        return {"authenticated": False}
    from app.models import UserSession
    from app.services.sessions import hash_session_token

    raw_token = request.cookies.get(SESSION_COOKIE_NAME) or ""
    session_row = (
        db.query(UserSession)
        .filter(
            UserSession.session_token_hash == hash_session_token(raw_token),
            UserSession.revoked_at.is_(None),
        )
        .one_or_none()
    )
    return {
        "authenticated": True,
        "user": {"id": current_user.id, "email": current_user.email},
        "remember_me": bool(session_row.remember_me) if session_row else False,
        "expires_at": session_row.expires_at.isoformat() if session_row else None,
    }


@router.post("/setup", response_model=TokenResponse)
def setup_admin(
    payload: SetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    if has_admin_user(db):
        raise HTTPException(status_code=400, detail="Administrator already configured")
    if len(payload.password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
    user = User(email=payload.email, hashed_password=hash_password(payload.password), is_admin=True)
    db.add(user)
    db.commit()
    mark_setup_complete(db)
    sync_evidence_registry(db)
    return _issue_session(
        response,
        db,
        user,
        remember_me=payload.remember_me,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    if not has_admin_user(db):
        raise HTTPException(status_code=403, detail="Setup required")
    try:
        assert_e2e_user_allowed(payload.email)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return _issue_session(
        response,
        db,
        user,
        remember_me=payload.remember_me,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    revoke_session_token(db, raw_token)
    _clear_session_cookie(response)
    return {"logged_out": True}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {"email": current_user.email, "id": current_user.id}


def bootstrap_admin_from_env(db: Session) -> None:
    """Create admin only when no admin exists — never overwrite password or delete users."""
    if has_admin_user(db):
        return
    if not (settings.admin_email and settings.admin_password):
        return
    if len(settings.admin_password) < 12:
        return
    user = User(
        email=settings.admin_email,
        hashed_password=hash_password(settings.admin_password),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    mark_setup_complete(db)
