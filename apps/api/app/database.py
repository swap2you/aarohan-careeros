from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings
from app.services.database_identity import (
    assert_connection_matches_identity,
    should_enforce_identity,
    validate_database_identity_marker,
)

_engine = None
_SessionLocalMaker = None


class Base(DeclarativeBase):
    pass


def get_engine():
    global _engine
    if _engine is None:
        url = settings.database_url
        if not url:
            raise RuntimeError("DATABASE_URL is required")
        if should_enforce_identity(url):
            assert_connection_matches_identity(url)
        _engine = create_engine(url, pool_pre_ping=True)
        if should_enforce_identity(url):
            validate_database_identity_marker(_engine, url)
    return _engine


def _sessionmaker():
    global _SessionLocalMaker
    if _SessionLocalMaker is None:
        _SessionLocalMaker = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocalMaker


class _SessionLocalProxy:
    def __call__(self):
        return _sessionmaker()()


SessionLocal = _SessionLocalProxy()


def __getattr__(name: str):
    if name == "engine":
        return get_engine()
    raise AttributeError(name)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
