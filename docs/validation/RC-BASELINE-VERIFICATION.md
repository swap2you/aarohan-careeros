# RC baseline verification (r2.13.0-rc1)

**Date:** 2026-06-29  
**Commit:** `edb540dfde8499b0b0f088c9d3f1d5689d691916`  
**Tag:** `r2.13.0-rc1`

## Git baseline

| Check | Result |
|-------|--------|
| Branch `main` | PASS |
| Working tree clean (at RC tag) | PASS |
| `origin/main` synced | PASS |
| `r2.13.0-rc1` → `edb540d` | PASS |
| Remote tags present (r2.0.0–r2.13.0-rc1) | PASS — no force-updates detected |
| Latest CI run | **28378806376** — **success** |

## Automated gate (`Verify-Full-R2.ps1`)

| Step | Result | Notes |
|------|--------|-------|
| git_clean | PASS | |
| tag_audit | PASS | |
| secret_scan | PASS | |
| prohibited_source_scan | PASS | |
| pytest (local SQLite) | 112 passed, 8 skipped | See skip table below |
| pytest (Docker PostgreSQL) | 8 passed | migration + duplicate integration |
| web build | PASS | |
| Playwright | **19 passed** | ~14.5s |
| docker_health | PASS | |

**Gate note:** Initial run failed due to pytest deprecation warnings on stderr (PowerShell false negative). Remediated in `Verify-Full-R2.ps1` for rc2.

**Total duration (full gate):** ~119s

## Skipped tests (local SQLite `DATABASE_URL`)

| Test | Reason | Equivalent validation |
|------|--------|----------------------|
| `test_duplicate_risk_postgres.py::test_same_requisition_red` | `skipif` — PostgreSQL required | Docker `test_duplicate_risk_postgres.py` (CI Postgres job) |
| `test_duplicate_risk_postgres.py::test_same_source_external_id_ingest_dedupes` | same | same |
| `test_duplicate_risk_postgres.py::test_description_fingerprint_red_same_company_role` | same | same |
| `test_duplicate_risk_postgres.py::test_override_requires_reason_and_audit` | same | same |
| `test_duplicate_risk_postgres.py::test_packet_generation_blocked_on_red` | same | same |
| `test_duplicate_risk_postgres.py::test_mark_submitted_records_ledger` | same | same |
| `test_duplicate_risk_postgres.py::test_spacing_caution_same_company` | same | same |
| `test_migrations.py::test_alembic_upgrade_downgrade_upgrade` | `skipif` — PostgreSQL required | Docker migration test (upgrade/downgrade/upgrade) |

Local default uses in-memory SQLite (`conftest.py`); PostgreSQL integration runs in CI and via `docker compose exec api pytest tests/test_migrations.py tests/test_duplicate_risk_postgres.py`.

## Operational note

Database missing `alembic_version` caused API restart loop after image rebuild. Resolved with `docker compose run --rm api alembic stamp head` (existing schema preserved). Document in startup runbook — not a schema defect if stamp is applied once.
