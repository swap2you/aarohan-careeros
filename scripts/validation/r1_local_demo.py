#!/usr/bin/env python3
"""R1 local validation demo against running API."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

API = os.environ.get("API_BASE", "http://localhost:8000")
ADMIN_EMAIL = os.environ.get("VALIDATION_ADMIN_EMAIL", "admin@aarohan.local")
ADMIN_PASSWORD = os.environ.get("VALIDATION_ADMIN_PASSWORD", "ValidationPass123!")


def main() -> int:
    results: dict = {"steps": [], "artifacts": {}}
    client = httpx.Client(base_url=API, timeout=120.0)
    passed = True

    def step(name: str, fn):
        nonlocal passed
        try:
            out = fn()
            results["steps"].append({"name": name, "ok": True, "detail": out})
            print(f"[PASS] {name}")
            return out
        except Exception as exc:
            passed = False
            results["steps"].append({"name": name, "ok": False, "error": str(exc)})
            print(f"[FAIL] {name}: {exc}")
            return None

    setup = client.get("/api/auth/setup-status").json()
    if setup.get("setup_required"):
        step(
            "admin_setup",
            lambda: client.post(
                "/api/auth/setup",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            ).json(),
        )
    token = step(
        "login",
        lambda: client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        ).json()["access_token"],
    )
    if not token:
        _write(results)
        return 1
    headers = {"Authorization": f"Bearer {token}"}

    step("integration_status", lambda: client.get("/api/integrations/status", headers=headers).json())
    connect = step(
        "google_connect_url",
        lambda: client.get("/api/integrations/google/connect?service=google", headers=headers).json(),
    )
    if connect and connect.get("auth_url"):
        results["artifacts"]["google_auth_url"] = connect["auth_url"]

    jobs = step("ingest_fixture", lambda: client.post("/api/jobs/ingest/fixture", headers=headers).json())
    if not jobs:
        _write(results)
        return 1
    job_id = jobs[0]["id"]

    app = step(
        "generate_packet",
        lambda: client.post(
            f"/api/applications/jobs/{job_id}/generate?resume_profile=qe_leadership",
            headers=headers,
        ).json(),
    )
    if app:
        results["artifacts"]["packet_paths"] = {
            "docx": app.get("resume_docx_path"),
            "pdf": app.get("resume_pdf_path"),
            "metadata_keys": list((app.get("packet_metadata") or {}).keys()),
        }

    step(
        "packet_preview",
        lambda: client.get(f"/api/validation/applications/{app['id']}/preview", headers=headers).json(),
    )

    folders1 = step(
        "drive_folders_run1",
        lambda: client.get("/api/integrations/google/drive/folders", headers=headers).json(),
    )
    folders2 = step(
        "drive_folders_run2",
        lambda: client.get("/api/integrations/google/drive/folders", headers=headers).json(),
    )
    if folders1 and folders2:
        results["artifacts"]["drive_idempotent"] = folders1.get("folders") == folders2.get("folders")
        results["artifacts"]["drive_folder_ids"] = folders2.get("folders")

    sync1 = step("gmail_sync_run1", lambda: client.post("/api/integrations/gmail/sync", headers=headers).json())
    sync2 = step("gmail_sync_run2", lambda: client.post("/api/integrations/gmail/sync", headers=headers).json())
    if sync1 and sync2:
        results["artifacts"]["gmail_dedup"] = sync2.get("processed", 1) == 0 or sync2.get("processed", 0) <= sync1.get("processed", 0)

    _write(results)
    return 0 if passed else 1


def _write(results: dict) -> None:
    out_path = Path("artifacts/r1_demo_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    raise SystemExit(main())
