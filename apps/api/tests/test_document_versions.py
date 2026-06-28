"""Immutable document version tests."""

from pathlib import Path

from fastapi.testclient import TestClient


def test_regenerate_after_submit_creates_v02(client: TestClient, auth_headers, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "generated_root", str(tmp_path / "generated"))

    job = client.post("/api/jobs/ingest/fixture", headers=auth_headers).json()[0]
    first = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers)
    assert first.status_code == 200
    app1 = first.json()
    v1_docx = app1["resume_docx_path"]
    v1_pdf = app1["resume_pdf_path"]

    submitted = client.post(
        f"/api/applications/{app1['id']}/actions",
        headers=auth_headers,
        json={"action": "mark_submitted"},
    )
    assert submitted.status_code == 200

    second = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers)
    assert second.status_code == 200
    app2 = second.json()
    assert app2["resume_docx_path"] != v1_docx
    assert Path(v1_docx).exists()
    assert Path(app2["resume_docx_path"]).exists()

    versions = client.get(f"/api/applications/{app1['id']}/versions", headers=auth_headers)
    assert versions.status_code == 200
    body = versions.json()
    assert len(body) >= 2
    assert body[0]["is_submitted_immutable"] is True
    assert body[-1]["version_number"] >= 2


def test_submitted_version_immutable_flag(client: TestClient, auth_headers):
    job = client.post("/api/jobs/ingest/fixture", headers=auth_headers).json()[0]
    app = client.post(f"/api/applications/jobs/{job['id']}/generate", headers=auth_headers).json()
    client.post(
        f"/api/applications/{app['id']}/actions",
        headers=auth_headers,
        json={"action": "mark_submitted"},
    )
    versions = client.get(f"/api/applications/{app['id']}/versions", headers=auth_headers).json()
    assert any(v["is_submitted_immutable"] for v in versions)
