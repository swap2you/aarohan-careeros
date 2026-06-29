from pathlib import Path

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_API_ROOT = Path(__file__).resolve().parents[1]
if (_API_ROOT / "config").exists():
    _REPO_ROOT = _API_ROOT
elif len(_API_ROOT.parents) > 1:
    _REPO_ROOT = _API_ROOT.parents[1]
else:
    _REPO_ROOT = _API_ROOT

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("APP_SECRET", "test-secret-key-32chars-minimum!")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key-32chars!")
os.environ.setdefault("ALLOW_LEGACY_JWT_AUTH", "true")
os.environ.setdefault("EXPOSE_SESSION_TOKEN_IN_LOGIN_RESPONSE", "true")
os.environ.setdefault("OAUTH_FIXTURE_MODE", "true")
os.environ.setdefault("GENERATED_ROOT", str(_API_ROOT / "generated"))
os.environ.setdefault("CONFIG_ROOT", str(_REPO_ROOT / "config"))
os.environ.setdefault("CAREER_VAULT_ROOT", str(_REPO_ROOT / "career_vault"))

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import EvidenceItem, User  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.config_loader import source_policy  # noqa: E402
from app.services.setup import mark_setup_complete  # noqa: E402


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    db.add(
        User(
            email="admin@test.local",
            hashed_password=hash_password("SecurePass123!"),
            is_admin=True,
        )
    )
    for evidence_id, statement in [
        ("PENNDOT_STACK", "Enterprise development across .NET, Java, Spring REST APIs."),
        ("ASCENSUS_SDET", "Ascensus Sr Principal SDET – Automation Framework Architect."),
        ("PERSISTENT_PROJECT_LEAD", "Persistent Systems Project Lead – QE Platform Architect."),
        ("TEAM_LEADERSHIP", "Leads four direct team members and offshore guidance."),
        ("MULTI_ROLE_DELIVERY", "Project leadership, Scrum facilitation, client communication."),
    ]:
        db.add(
            EvidenceItem(
                evidence_id=evidence_id,
                category="technical",
                statement=statement,
                status="USER_CONFIRMED",
                public_use=True,
            )
        )
    mark_setup_complete(db)
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with (
        patch("app.main.run_migrations"),
        patch("app.main.bootstrap_admin_from_env"),
        patch("app.main.sync_evidence_registry"),
        TestClient(app) as test_client,
    ):
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@test.local", "password": "SecurePass123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
