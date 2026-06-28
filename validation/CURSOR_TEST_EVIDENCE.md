# Cursor Test Evidence — Finalize Main Sync

Date: 2026-06-27

## Commands and results

| Step | Command | Result |
|------|---------|--------|
| Secret scan | `python scripts/validation/secret_scan.py` | PASSED |
| Prohibited source scan | `python scripts/validation/prohibited_source_scan.py` | PASSED |
| Backend pytest | `pytest -q` (apps/api) | **24 passed**, 1 skipped |
| Frontend build | `npm run build` (apps/web) | SUCCESS (16 routes) |
| Docker compose | `docker compose build/up` | BLOCKED — Docker not installed (admin UAC required) |
| Playwright E2E | `npm run test:e2e` | NOT RUN — stack not up without Docker |
| gh CLI | `gh run watch` | NOT AVAILABLE — install blocked without admin |

## Test modules

- `test_core.py` — 13 tests
- `test_oauth.py` — 6 tests
- `test_google_integration.py` — 5 tests
- `test_migrations.py` — 1 skipped locally (PostgreSQL required; runs in CI)

## CI expectation

GitHub Actions workflow `.github/workflows/ci.yml`:
- api-tests (pytest + Postgres service)
- validation-scans
- web-build
