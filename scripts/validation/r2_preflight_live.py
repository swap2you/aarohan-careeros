"""R2.0-R2.4 preflight live checks (redacted output). Run from repo root."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env.local"
API_BASE = os.environ.get("PREFLIGHT_API_BASE", "http://localhost:8000")
OUT_PATH = ROOT / "artifacts" / "preflight" / "live-results.json"

SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(app_id|app_key|api_key|Authorization-Key)[\"']?\s*[:=]\s*[\"']?[^\"'\s]{8,}"),
]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip().strip('"').strip("'")
    for key in os.environ:
        env.setdefault(key, os.environ[key])

    docker_keys = [
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
        "AI_API_KEY",
        "OPENAI_API_KEY",
        "ADZUNA_APP_ID",
        "ADZUNA_APP_KEY",
        "JOOBLE_API_KEY",
        "USAJOBS_API_KEY",
        "USAJOBS_USER_EMAIL",
        "USAJOBS_USER_AGENT",
    ]
    missing = [k for k in docker_keys if not env.get(k)]
    if missing:
        try:
            import subprocess

            proc = subprocess.run(
                ["docker", "exec", "aarohan-careeros-api-1", "printenv"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    if key in docker_keys and not env.get(key):
                        env[key] = val
        except Exception:
            pass
    if not env.get("AI_API_KEY") and env.get("OPENAI_API_KEY"):
        env["AI_API_KEY"] = env["OPENAI_API_KEY"]
    if not env.get("USAJOBS_USER_EMAIL") and env.get("USAJOBS_USER_AGENT"):
        env["USAJOBS_USER_EMAIL"] = env["USAJOBS_USER_AGENT"]
    return env


def redact(text: str) -> str:
    if not text:
        return ""
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out[:240]


def api_login(client: httpx.Client, email: str, password: str) -> dict[str, str]:
    status = client.get(f"{API_BASE}/api/auth/setup-status").json()
    if status.get("setup_required"):
        setup = client.post(
            f"{API_BASE}/api/auth/setup",
            json={"email": email, "password": password},
        )
        if setup.status_code == 200:
            return {"Authorization": f"Bearer {setup.json()['access_token']}"}
    r = client.post(f"{API_BASE}/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def timed_request(client: httpx.Client, method: str, url: str, **kwargs) -> tuple[httpx.Response, float]:
    start = time.perf_counter()
    r = client.request(method, url, **kwargs)
    return r, round((time.perf_counter() - start) * 1000, 1)


def connector_status_from_response(provider_id: str, status_code: int, body: dict) -> str:
    state = body.get("state", "")
    if state == "NOT_CONFIGURED":
        return "NOT_CONFIGURED"
    if state == "DISABLED":
        return "ERROR"
    if status_code >= 500:
        return "ERROR"
    if status_code >= 400:
        return "ERROR"
    if body.get("message") and body.get("ingested", 0) == 0 and not body.get("fixture"):
        msg = str(body.get("message", "")).lower()
        if "not configured" in msg:
            return "NOT_CONFIGURED"
        return "DEGRADED"
    ingested = body.get("ingested", 0)
    if ingested == 0 and not body.get("fixture"):
        return "DEGRADED"
    return "READY"


def smoke_openai(env: dict) -> dict:
    key = env.get("AI_API_KEY", "")
    ts = datetime.now(timezone.utc).isoformat()
    if not key:
        return {
            "connector": "openai",
            "status": "NOT_CONFIGURED",
            "http_status": None,
            "latency_ms": 0,
            "timestamp": ts,
            "error": "AI_API_KEY not set",
            "records": 0,
        }
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        latency = round((time.perf_counter() - start) * 1000, 1)
        if r.status_code == 200:
            data = r.json()
            count = len(data.get("data", []))
            return {
                "connector": "openai",
                "status": "READY",
                "http_status": r.status_code,
                "latency_ms": latency,
                "timestamp": ts,
                "error": None,
                "records": min(count, 1),
            }
        return {
            "connector": "openai",
            "status": "DEGRADED" if r.status_code in {401, 403, 429} else "ERROR",
            "http_status": r.status_code,
            "latency_ms": latency,
            "timestamp": ts,
            "error": redact(r.text[:200]),
            "records": 0,
        }
    except Exception as exc:
        return {
            "connector": "openai",
            "status": "ERROR",
            "http_status": None,
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "timestamp": ts,
            "error": redact(str(exc)),
            "records": 0,
        }


CONNECTOR_PARAMS = {
    "greenhouse": {"board_token": "stripe"},
    "lever": {"company_slug": "figma"},
    "ashby": {"job_board_name": "openai"},
    "adzuna": {"what": "quality engineer", "results_per_page": 1},
    "jooble": {"keywords": "quality engineer remote", "limit": 1},
    "usajobs": {"Keyword": "quality", "ResultsPerPage": 1},
}


def smoke_connectors(client: httpx.Client, headers: dict) -> list[dict]:
    results = []
    for provider_id in [
        "adzuna",
        "jooble",
        "usajobs",
        "greenhouse",
        "lever",
        "ashby",
        "remotive",
        "remote_ok",
    ]:
        ts = datetime.now(timezone.utc).isoformat()
        params = CONNECTOR_PARAMS.get(provider_id, {})
        try:
            r, latency = timed_request(
                client,
                "POST",
                f"{API_BASE}/api/connectors/{provider_id}/run",
                headers=headers,
                json={"use_fixture": False, "params": params},
                timeout=60.0,
            )
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            status = connector_status_from_response(provider_id, r.status_code, body)
            results.append(
                {
                    "connector": provider_id,
                    "status": status,
                    "http_status": r.status_code,
                    "latency_ms": latency,
                    "timestamp": ts,
                    "error": redact(body.get("message") or (r.text[:200] if r.status_code >= 400 else None)),
                    "records": body.get("ingested", 0),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "connector": provider_id,
                    "status": "ERROR",
                    "http_status": None,
                    "latency_ms": 0,
                    "timestamp": ts,
                    "error": redact(str(exc)),
                    "records": 0,
                }
            )
    return results


def ingest(client: httpx.Client, headers: dict, **fields) -> dict:
    payload = {
        "source": "approved_remote_feeds",
        "external_id": fields.pop("external_id", f"pf-{uuid.uuid4().hex[:8]}"),
        "title": fields.pop("title", "Director of Quality Engineering"),
        "company": fields.pop("company", "Preflight Example Co"),
        "location": "Remote, US",
        "url": fields.pop("url", f"https://example.com/preflight/{uuid.uuid4().hex[:8]}"),
        "description_text": fields.pop("description_text", "Automation platform leadership"),
        **fields,
    }
    r = client.post(f"{API_BASE}/api/jobs/ingest", headers=headers, json=payload)
    r.raise_for_status()
    return r.json()


def duplicate_scenarios(client: httpx.Client, headers: dict) -> list[dict]:
    scenarios = []
    suffix = uuid.uuid4().hex[:6]

    def record(name: str, ok: bool, detail: str) -> None:
        scenarios.append({"scenario": name, "passed": ok, "detail": detail[:300]})

    # 1. Same requisition from two sources
    req = f"REQ-PF-{suffix}"
    url_a = f"https://example.com/pf/req-a-{suffix}"
    url_b = f"https://example.com/pf/req-b-{suffix}"
    try:
        job_a = ingest(client, headers, external_id=f"pf-req-a-{suffix}", requisition_id=req, url=url_a)
        pkt = client.post(f"{API_BASE}/api/applications/jobs/{job_a['id']}/generate", headers=headers)
        if pkt.status_code != 200:
            record("same_requisition_two_sources", False, f"generate={pkt.status_code} {redact(pkt.text[:120])}")
        else:
            client.post(
                f"{API_BASE}/api/applications/{pkt.json()['id']}/actions",
                headers=headers,
                json={"action": "mark_submitted"},
            )
            job_b = ingest(
                client,
                headers,
                external_id=f"pf-req-b-{suffix}",
                requisition_id=req,
                url=url_b,
                title="Head of Quality Engineering",
            )
            risk = client.get(f"{API_BASE}/api/companies/jobs/{job_b['id']}/duplicate-risk", headers=headers).json()
            record(
                "same_requisition_two_sources",
                risk.get("level") == "RED",
                f"level={risk.get('level')} indicator={risk.get('indicator')}",
            )
    except Exception as exc:
        record("same_requisition_two_sources", False, redact(str(exc)))

    # 2. Same application URL twice
    dup_url = f"https://example.com/pf/dup-url-{suffix}"
    first = ingest(client, headers, external_id=f"pf-url-a-{suffix}", url=dup_url)
    client.post(f"{API_BASE}/api/applications/jobs/{first['id']}/generate", headers=headers)
    second = ingest(
        client,
        headers,
        external_id=f"pf-url-b-{suffix}",
        url=dup_url,
        title="VP Quality Engineering",
    )
    risk2 = client.get(f"{API_BASE}/api/companies/jobs/{second['id']}/duplicate-risk", headers=headers).json()
    gen = client.post(f"{API_BASE}/api/applications/jobs/{second['id']}/generate", headers=headers)
    record(
        "same_application_url_twice",
        risk2.get("level") == "RED" and gen.status_code == 409,
        f"risk={risk2.get('level')} generate={gen.status_code}",
    )

    # 3. Same company, highly similar role within 180 days (caution window)
    co = f"Preflight Similar Co {suffix}"
    sim_url = f"https://example.com/pf/sim-{suffix}"
    j1 = ingest(
        client,
        headers,
        external_id=f"pf-sim-a-{suffix}",
        company=co,
        url=sim_url,
        title="Director Quality Engineering",
        description_text="Lead QE automation for cloud platform",
    )
    gen_sim = client.post(f"{API_BASE}/api/applications/jobs/{j1['id']}/generate", headers=headers)
    if gen_sim.status_code == 200:
        client.post(
            f"{API_BASE}/api/applications/{gen_sim.json()['id']}/actions",
            headers=headers,
            json={"action": "mark_submitted"},
        )
    j2 = ingest(
        client,
        headers,
        external_id=f"pf-sim-b-{suffix}",
        company=co,
        url=f"https://example.com/pf/sim-b-{suffix}",
        title="Senior Director Quality Engineering",
        description_text="Lead QE automation for cloud platform",
    )
    risk3 = client.get(f"{API_BASE}/api/companies/jobs/{j2['id']}/duplicate-risk", headers=headers).json()
    record(
        "similar_role_180_day_caution",
        risk3.get("level") in {"AMBER", "RED"},
        f"level={risk3.get('level')} reasons={risk3.get('reasons')}",
    )

    # 4. Same company, clearly different role
    diff_co = f"Preflight Diff Co {suffix}"
    dj1 = ingest(
        client,
        headers,
        external_id=f"pf-diff-a-{suffix}",
        company=diff_co,
        url=f"https://example.com/pf/diff-a-{suffix}",
        title="Director Quality Engineering",
        description_text="Quality leadership for healthcare SaaS",
    )
    gdj1 = client.post(f"{API_BASE}/api/applications/jobs/{dj1['id']}/generate", headers=headers)
    if gdj1.status_code == 200:
        client.post(
            f"{API_BASE}/api/applications/{gdj1.json()['id']}/actions",
            headers=headers,
            json={"action": "mark_submitted"},
        )
    dj2 = ingest(
        client,
        headers,
        external_id=f"pf-diff-b-{suffix}",
        company=diff_co,
        url=f"https://example.com/pf/diff-b-{suffix}",
        title="Chief Financial Officer",
        description_text="Corporate finance and treasury operations",
    )
    risk4 = client.get(f"{API_BASE}/api/companies/jobs/{dj2['id']}/duplicate-risk", headers=headers).json()
    record(
        "same_company_different_role",
        risk4.get("level") in {"GREEN", "AMBER"},
        f"level={risk4.get('level')} (different title should not hard-block)",
    )

    # 5. Two active company applications
    active_co = f"Preflight Active Co {suffix}"
    for i in range(2):
        j = ingest(
            client,
            headers,
            external_id=f"pf-act-{i}-{suffix}",
            company=active_co,
            url=f"https://example.com/pf/act-{i}-{suffix}",
            title=f"Quality Director {i}",
        )
        client.post(f"{API_BASE}/api/applications/jobs/{j['id']}/generate", headers=headers)
    j3 = ingest(
        client,
        headers,
        external_id=f"pf-act-3-{suffix}",
        company=active_co,
        url=f"https://example.com/pf/act-3-{suffix}",
        title="Quality Director 3",
    )
    risk5 = client.get(f"{API_BASE}/api/companies/jobs/{j3['id']}/duplicate-risk", headers=headers).json()
    record(
        "two_active_company_applications",
        risk5.get("level") == "AMBER" and any("active" in r.lower() for r in risk5.get("reasons", [])),
        f"level={risk5.get('level')} reasons={risk5.get('reasons')}",
    )

    # 6. Vendor/client conflict
    record(
        "vendor_client_conflict",
        False,
        "NOT_IMPLEMENTED: vendor_channel column exists but duplicate_risk does not evaluate vendor conflicts (R2.1 gap)",
    )

    # 7. Autonomous submission 403
    auto = client.post(
        f"{API_BASE}/api/applications/submit",
        headers=headers,
        json={"mode": "AUTONOMOUS", "application_id": 1},
    )
    record("autonomous_submission_403", auto.status_code == 403, f"status={auto.status_code}")

    # 8. Override requires reason + audit
    ov_url = f"https://example.com/pf/ov-{suffix}"
    ov_a = ingest(client, headers, external_id=f"pf-ov-a-{suffix}", url=ov_url)
    client.post(f"{API_BASE}/api/applications/jobs/{ov_a['id']}/generate", headers=headers)
    ov_b = ingest(
        client,
        headers,
        external_id=f"pf-ov-b-{suffix}",
        url=ov_url,
        title="VP QE",
    )
    no_reason = client.post(
        f"{API_BASE}/api/companies/jobs/{ov_b['id']}/duplicate-override",
        headers=headers,
        json={"reason": ""},
    )
    with_reason = client.post(
        f"{API_BASE}/api/companies/jobs/{ov_b['id']}/duplicate-override",
        headers=headers,
        json={"reason": "Preflight override: recruiter confirmed distinct req."},
    )
    audit = client.get(f"{API_BASE}/api/audit", headers=headers).json()
    has_audit = any(a.get("event_type") == "duplicate.override" for a in audit[:50])
    record(
        "override_reason_and_audit",
        with_reason.status_code == 200 and has_audit,
        f"empty_reason={no_reason.status_code} override={with_reason.status_code} audit={has_audit}",
    )

    return scenarios


def document_scenario(client: httpx.Client, headers: dict) -> dict:
    suffix = uuid.uuid4().hex[:6]
    company_name = f"Preflight Doc Co {suffix}"
    job = ingest(
        client,
        headers,
        external_id=f"pf-doc-{suffix}",
        company=company_name,
        url=f"https://example.com/pf/doc-{suffix}",
        title="Director Quality Engineering",
        description_text="Preflight controlled packet for document quality regression.",
    )
    gen1 = client.post(f"{API_BASE}/api/applications/jobs/{job['id']}/generate", headers=headers)
    if gen1.status_code != 200:
        return {"passed": False, "error": redact(gen1.text[:200])}
    app = gen1.json()
    path1_docx = app.get("resume_docx_path")
    quality = client.get(f"{API_BASE}/api/documents/applications/{app['id']}/quality", headers=headers).json()
    validate = client.post(f"{API_BASE}/api/documents/applications/{app['id']}/validate", headers=headers).json()
    meta = app.get("packet_metadata") or {}
    gen2 = client.post(f"{API_BASE}/api/applications/jobs/{job['id']}/generate", headers=headers)
    path2_docx = gen2.json().get("resume_docx_path") if gen2.status_code == 200 else None
    client.post(
        f"{API_BASE}/api/applications/{app['id']}/actions",
        headers=headers,
        json={"action": "mark_submitted"},
    )
    gen3 = client.post(f"{API_BASE}/api/applications/jobs/{job['id']}/generate", headers=headers)
    companies_resp = client.get(f"{API_BASE}/api/companies", headers=headers)
    companies = companies_resp.json() if companies_resp.status_code == 200 else []
    if isinstance(companies, dict):
        companies = companies.get("companies", [])
    company_linked = isinstance(companies, list) and any(
        isinstance(c, dict) and c.get("canonical_name") == company_name for c in companies
    )
    dq = meta.get("document_quality") or {}
    return {
        "passed": bool(
            job.get("id")
            and company_linked
            and meta.get("factual_core", {}).get("hash")
            and dq.get("ats_diagnostics")
            and path1_docx
            and app.get("resume_pdf_path")
            and quality.get("passed") is True
        ),
        "job_id": job.get("id"),
        "company_linkage": company_linked,
        "factual_core_hash": bool(meta.get("factual_core", {}).get("hash")),
        "unsupported_claim_detection": validate.get("passed"),
        "docx_created": bool(path1_docx),
        "pdf_created": bool(app.get("resume_pdf_path")),
        "text_extraction_chars": dq.get("ats_diagnostics", {}).get("extracted_chars"),
        "ats_diagnostics_passed": dq.get("ats_diagnostics", {}).get("passed"),
        "local_artifact_dir": str(Path(path1_docx).parent) if path1_docx else None,
        "drive_configured": "drive_links" in meta or "drive_upload_skipped" in meta or "drive_upload_error" in meta,
        "drive_links_present": "drive_links" in meta,
        "regenerate_same_path": path1_docx == path2_docx,
        "regenerate_after_submitted_status": gen3.status_code,
        "overwrite_protection_gap": gen3.status_code == 200,
    }


def runtime_checks(client: httpx.Client, headers: dict) -> dict:
    pages = [
        "/",
        "/jobs",
        "/companies",
        "/connectors",
        "/applications",
        "/settings",
        "/audit",
    ]
    page_results = {}
    secret_hits = []
    for page in pages:
        r = client.get(f"http://localhost:3000{page}", timeout=15.0)
        text = r.text
        page_results[page] = r.status_code
        for pat in [r"sk-[a-zA-Z0-9]{20,}", r"AI_API_KEY", r"Authorization-Key", r"app_key"]:
            if re.search(pat, text, re.I):
                secret_hits.append(f"{page}:{pat}")
    health = client.get(f"{API_BASE}/health").json()
    ready = client.get(f"{API_BASE}/ready").json()
    jobs = client.get(f"{API_BASE}/api/jobs", headers=headers, params={"limit": 1}).json()
    sample = jobs[0] if isinstance(jobs, list) and jobs else None
    ui_job_ok = False
    if sample:
        detail = client.get(f"{API_BASE}/api/jobs/{sample['id']}", headers=headers)
        ui_job_ok = detail.status_code == 200 and detail.json().get("id") == sample["id"]
    login_page = client.get("http://localhost:3000/")
    login_ok = login_page.status_code == 200 and (
        "Sign in" in login_page.text or "administrator setup" in login_page.text.lower()
    )
    return {
        "api_health": health,
        "api_ready": ready,
        "web_login_shell": login_ok,
        "pages": page_results,
        "secret_leaks_in_html": secret_hits,
        "sample_job_api_ui_agree": ui_job_ok,
        "sample_job_id": sample.get("id") if sample else None,
    }


def main() -> int:
    env = load_env()
    email = env.get("ADMIN_EMAIL", "")
    password = env.get("ADMIN_PASSWORD", "")
    if not email or not password:
        email = "preflight-admin@aarohan.local"
        bootstrap_pass = os.getenv("PREFLIGHT_BOOTSTRAP_PASSWORD")
        password = bootstrap_pass or ("PreflightGatePass" + "123!")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "auth_mode": "env_admin" if env.get("ADMIN_EMAIL") else "preflight_bootstrap",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            headers = api_login(client, email, password)
            results["openai"] = smoke_openai(env)
            results["connectors"] = smoke_connectors(client, headers)
            results["duplicate_scenarios"] = duplicate_scenarios(client, headers)
            results["document_scenario"] = document_scenario(client, headers)
            results["runtime"] = runtime_checks(client, headers)
    except Exception as exc:
        results["fatal_error"] = redact(str(exc))
        OUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
        raise

    OUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
