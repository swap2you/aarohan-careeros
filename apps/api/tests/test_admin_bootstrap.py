"""Admin bootstrap must never overwrite existing credentials."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.routers.auth import bootstrap_admin_from_env
from app.services.auth import hash_password, verify_password


def test_bootstrap_preserves_existing_admin_password():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.models import User

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        original_pwd = "OriginalPass123!"
        db.add(
            User(
                email="owner@test.local",
                hashed_password=hash_password(original_pwd),
                is_admin=True,
            )
        )
        db.commit()
        alt_pwd = "TotallyDifferentPass999!"
        with patch("app.routers.auth.settings") as mock_settings:
            mock_settings.admin_email = "owner@test.local"
            mock_settings.admin_password = alt_pwd
            bootstrap_admin_from_env(db)
        user = db.query(User).filter(User.email == "owner@test.local").one()
        assert verify_password(original_pwd, user.hashed_password)
        assert not verify_password(alt_pwd, user.hashed_password)
    finally:
        db.close()


def test_bootstrap_creates_admin_only_when_database_empty():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.models import User
    from app.services.setup import has_admin_user

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        assert not has_admin_user(db)
        init_pwd = "SecurePass123!"
        with patch("app.routers.auth.settings") as mock_settings:
            mock_settings.admin_email = "newadmin@test.local"
            mock_settings.admin_password = init_pwd
            bootstrap_admin_from_env(db)
        user = db.query(User).filter(User.email == "newadmin@test.local").one()
        assert user.is_admin
        assert verify_password(init_pwd, user.hashed_password)
    finally:
        db.close()


def test_login_succeeds_after_bootstrap_attempt(client: TestClient):
    pwd = "SecurePass123!"
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@test.local", "password": pwd, "remember_me": True},
    )
    assert login.status_code == 200
