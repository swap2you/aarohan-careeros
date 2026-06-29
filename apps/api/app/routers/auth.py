from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_optional_user
from app.models import User
from app.schemas import LoginRequest, SessionResponse, SetupRequest
from app.services.auth import hash_password, verify_password
from app.services.career_vault import sync_evidence_registry
from app.services.session_auth import (
    clear_session_cookie,
    create_session,
    get_session_token,
    resolve_session,
    revoke_session,
    set_session_cookie,
)
from app.services.setup import has_admin_user, is_setup_complete, mark_setup_complete

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_response(user: User, session_row) -> SessionResponse:
    return SessionResponse(
        authenticated=True,
        email=user.email,
        user_id=user.id,
        remember_me=session_row.remember_me if session_row else False,
        expires_at=session_row.expires_at.isoformat() if session_row else None,
    )


@router.get("/setup-status")
def setup_status(db: Session = Depends(get_db)) -> dict:
    return {
        "setup_required": not is_setup_complete(db) and not has_admin_user(db),
        "has_admin": has_admin_user(db),
    }


@router.get("/session", response_model=SessionResponse)
def auth_session(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> SessionResponse:
    if not user:
        return SessionResponse(authenticated=False)
    raw = get_session_token(request)
    row = resolve_session(db, raw) if raw else None
    if raw and not row:
        return SessionResponse(authenticated=False)
    return _session_response(user, row)


@router.post("/setup", response_model=SessionResponse)
def setup_admin(
    payload: SetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    if has_admin_user(db):
        raise HTTPException(status_code=400, detail="Administrator already configured")
    if len(payload.password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
    user = User(email=payload.email, hashed_password=hash_password(payload.password), is_admin=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    mark_setup_complete(db)
    sync_evidence_registry(db)
    remember = payload.remember_me if payload.remember_me is not None else True
    raw, row = create_session(db, user, remember_me=remember, user_agent=request.headers.get("user-agent"))
    set_session_cookie(response, raw, remember_me=remember)
    return _session_response(user, row)


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    if not has_admin_user(db):
        raise HTTPException(status_code=403, detail="Setup required")
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    remember = payload.remember_me if payload.remember_me is not None else True
    raw, row = create_session(db, user, remember_me=remember, user_agent=request.headers.get("user-agent"))
    set_session_cookie(response, raw, remember_me=remember)
    return _session_response(user, row)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    revoke_session(db, get_session_token(request))
    clear_session_cookie(response)
    return {"logged_out": True}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {"email": current_user.email, "id": current_user.id}


def bootstrap_admin_from_env(db: Session) -> None:
    if has_admin_user(db):
        return
    if settings.admin_email and settings.admin_password and len(settings.admin_password) >= 12:
        user = User(
            email=settings.admin_email,
            hashed_password=hash_password(settings.admin_password),
            is_admin=True,
        )
        db.add(user)
        db.commit()
        mark_setup_complete(db)
