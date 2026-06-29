"""PostgreSQL duplicate enforcement integration tests."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="PostgreSQL required for duplicate integration tests",
)


@pytest.fixture()
def pg_client():
    from app.database import Base, get_db
    from app.main import app
    from app.models import EvidenceItem, User
    from app.services.auth import hash_password
    from app.services.setup import mark_setup_complete

    engine = create_engine(os.environ["DATABASE_URL"])
    from tests.postgres_utils import reset_public_schema

    reset_public_schema(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(email="pg@test.local", hashed_password=hash_password("SecurePass123!"), is_admin=True))
    for eid, stmt in [
        ("PENNDOT_STACK", "Enterprise development across .NET, Java, Spring REST APIs."),
        ("ASCENSUS_SDET", "Ascensus Sr Principal SDET – Automation Framework Architect."),
        ("PERSISTENT_PROJECT_LEAD", "Persistent Systems Project Lead – QE Platform Architect."),
        ("TEAM_LEADERSHIP", "Leads four direct team members and offshore guidance."),
        ("MULTI_ROLE_DELIVERY", "Project leadership, Scrum facilitation, client communication."),
    ]:
        db.add(
            EvidenceItem(
                evidence_id=eid,
                category="technical",
                statement=stmt,
                status="USER_CONFIRMED",
                public_use=True,
            )
        )
    mark_setup_complete(db)
    db.commit()
    db.close()

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    from unittest.mock import patch

    app.dependency_overrides[get_db] = override_get_db
    with (
        patch("app.main.run_migrations"),
        patch("app.main.bootstrap_admin_from_env"),
        patch("app.main.sync_evidence_registry"),
        TestClient(app) as client,
    ):
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def pg_auth(pg_client: TestClient) -> dict[str, str]:
    response = pg_client.post(
        "/api/auth/login",
        json={"email": "pg@test.local", "password": "SecurePass123!"},
    )
    assert response.status_code == 200
    return {}


def _ingest(client: TestClient, headers: dict, **fields) -> dict:
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "source": fields.pop("source", "approved_remote_feeds"),
        "external_id": fields.pop("external_id", f"pg-{suffix}"),
        "title": fields.pop("title", "Director of Quality Engineering"),
        "company": fields.pop("company", f"PG Test Co {suffix}"),
        "location": "Remote, US",
        "url": fields.pop("url", f"https://example.com/pg/{suffix}"),
        "description_text": fields.pop("description_text", "PostgreSQL integration test job"),
        **fields,
    }
    response = client.post("/api/jobs/ingest", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _generate(client: TestClient, headers: dict, job_id: int) -> dict:
    response = client.post(f"/api/applications/jobs/{job_id}/generate", headers=headers)
    return response


class TestPostgresExactDuplicates:
    def test_same_url_red_globally_cross_company(self, pg_client, pg_auth):
        url = f"https://example.com/pg/shared-url-{uuid.uuid4().hex[:6]}"
        first = _ingest(pg_client, pg_auth, company="Company Alpha", url=url)
        assert _generate(pg_client, pg_auth, first["id"]).status_code == 200

        second = _ingest(
            pg_client,
            pg_auth,
            company="Company Beta Completely Different",
            url=url,
            title="VP Quality Engineering",
        )
        risk = pg_client.get(f"/api/companies/jobs/{second['id']}/duplicate-risk", headers=pg_auth)
        assert risk.json()["level"] == "RED"
        blocked = _generate(pg_client, pg_auth, second["id"])
        assert blocked.status_code == 409

    def test_same_requisition_red(self, pg_client, pg_auth):
        req = f"REQ-PG-{uuid.uuid4().hex[:6]}"
        co = f"PG Requisition Co {uuid.uuid4().hex[:4]}"
        first = _ingest(pg_client, pg_auth, company=co, requisition_id=req, url=f"https://example.com/pg/a-{req}")
        gen = _generate(pg_client, pg_auth, first["id"])
        assert gen.status_code == 200
        pg_client.post(
            f"/api/applications/{gen.json()['id']}/actions",
            headers=pg_auth,
            json={"action": "mark_submitted"},
        )

        second = _ingest(
            pg_client,
            pg_auth,
            company=co,
            requisition_id=req,
            url=f"https://example.com/pg/b-{req}",
            title="Head of QE",
        )
        assert pg_client.get(f"/api/companies/jobs/{second['id']}/duplicate-risk", headers=pg_auth).json()["level"] == "RED"

    def test_same_source_external_id_ingest_dedupes(self, pg_client, pg_auth):
        ext = f"ext-{uuid.uuid4().hex[:6]}"
        first = _ingest(pg_client, pg_auth, source="greenhouse_public_get", external_id=ext)
        gen = _generate(pg_client, pg_auth, first["id"])
        assert gen.status_code == 200
        app_id = gen.json()["id"]

        second = _ingest(
            pg_client,
            pg_auth,
            source="greenhouse_public_get",
            external_id=ext,
            company="Different Name Same Source ID",
            url=f"https://example.com/pg/source-{ext}",
        )
        assert second["id"] == first["id"]
        gen_again = _generate(pg_client, pg_auth, second["id"])
        assert gen_again.status_code == 200
        assert gen_again.json()["id"] == app_id

    def test_unrelated_ledger_does_not_affect_exact_url(self, pg_client, pg_auth):
        noise = _ingest(pg_client, pg_auth, company="Unrelated Noise Co")
        assert _generate(pg_client, pg_auth, noise["id"]).status_code == 200

        url = f"https://example.com/pg/isolated-{uuid.uuid4().hex[:6]}"
        target = _ingest(pg_client, pg_auth, url=url)
        assert pg_client.get(f"/api/companies/jobs/{target['id']}/duplicate-risk", headers=pg_auth).json()["level"] == "GREEN"

    def test_same_ats_job_id_red(self, pg_client, pg_auth):
        ats = f"ats-pg-{uuid.uuid4().hex[:6]}"
        first = _ingest(pg_client, pg_auth, ats_job_id=ats, url=f"https://example.com/pg/ats-a-{ats}")
        assert _generate(pg_client, pg_auth, first["id"]).status_code == 200

        second = _ingest(
            pg_client,
            pg_auth,
            ats_job_id=ats,
            company="Different ATS Company",
            url=f"https://example.com/pg/ats-b-{ats}",
        )
        assert pg_client.get(f"/api/companies/jobs/{second['id']}/duplicate-risk", headers=pg_auth).json()["level"] == "RED"
        assert _generate(pg_client, pg_auth, second["id"]).status_code == 409

    def test_description_fingerprint_red_same_company_role(self, pg_client, pg_auth):
        desc = f"Unique PostgreSQL fingerprint test description {uuid.uuid4().hex[:8]}"
        co = f"FP Co {uuid.uuid4().hex[:4]}"
        title = "Director of Quality Engineering"
        first = _ingest(pg_client, pg_auth, company=co, title=title, description_text=desc, location="Remote, US")
        gen = _generate(pg_client, pg_auth, first["id"])
        assert gen.status_code == 200
        pg_client.post(
            f"/api/applications/{gen.json()['id']}/actions",
            headers=pg_auth,
            json={"action": "mark_submitted"},
        )

        second = _ingest(
            pg_client,
            pg_auth,
            company=co,
            title=title,
            description_text=desc,
            location="Hybrid, Boston",
            external_id=f"fp-b-{uuid.uuid4().hex[:6]}",
            url=f"https://example.com/pg/fp-{uuid.uuid4().hex[:6]}",
        )
        risk = pg_client.get(f"/api/companies/jobs/{second['id']}/duplicate-risk", headers=pg_auth)
        assert risk.json()["level"] == "RED"
        assert _generate(pg_client, pg_auth, second["id"]).status_code == 409

    def test_override_requires_reason_and_audit(self, pg_client, pg_auth):
        url = f"https://example.com/pg/override-{uuid.uuid4().hex[:6]}"
        first = _ingest(pg_client, pg_auth, url=url)
        assert _generate(pg_client, pg_auth, first["id"]).status_code == 200
        second = _ingest(pg_client, pg_auth, url=url, title="Override role")
        empty = pg_client.post(
            f"/api/companies/jobs/{second['id']}/duplicate-override",
            headers=pg_auth,
            json={"reason": "short"},
        )
        assert empty.status_code == 422
        ok = pg_client.post(
            f"/api/companies/jobs/{second['id']}/duplicate-override",
            headers=pg_auth,
            json={"reason": "Recruiter confirmed this is a distinct requisition."},
        )
        assert ok.status_code == 200
        audit = pg_client.get("/api/audit", headers=pg_auth).json()
        assert any(row.get("event_type") == "duplicate.override" for row in audit)
