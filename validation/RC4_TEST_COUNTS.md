# RC4 Canonical Test Counts

This document resolves reported pytest count discrepancies and defines the canonical commands for the RC4 validation gate.

## Why counts differed

| Report | Count | Environment | Explanation |
|--------|-------|-------------|-------------|
| Docker `pytest` (owner stack) | **125 passed** | PostgreSQL `career_os`, migration head | Full suite after stabilization commits including `test_application_summary` and `test_job_detail` |
| Earlier host `pytest` | **116 passed, 8 skipped** | SQLite in-memory via `conftest.py` | Host Python without `sqlalchemy` installed failed import; when run correctly in CI, skipped tests are PostgreSQL-only integration cases |
| Playwright E2E | **21 passed** | CI ephemeral Postgres + fixture mode API | Does not touch owner local database |

**Canonical rule:** Report API counts from **`docker compose exec api pytest -q`** against PostgreSQL with migrations at head.

## Canonical commands (pre-RC4 gate)

### API — SQLite (unit, CI job `api-tests`)

```bash
cd apps/api
DATABASE_URL=sqlite+pysqlite:///:memory: \
APP_SECRET=ci-test-secret-key-32chars-minimum! \
TOKEN_ENCRYPTION_KEY=ci-test-token-encryption-key-32chars! \
OAUTH_FIXTURE_MODE=true \
pytest -q
```

Expected: all non-postgres tests pass; postgres-marked tests skip.

### API — PostgreSQL (owner / Docker)

```bash
docker compose exec api alembic upgrade head
docker compose exec api pytest -q
```

Expected: **125+ passed** (increases as stabilization tests are added).

### Migrations

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
docker compose exec api alembic upgrade head
```

### Playwright (isolated — recommended local)

```bash
pwsh scripts/local/Start-Aarohan-E2E.ps1
cd apps/web
$env:PLAYWRIGHT_API_BASE='http://localhost:8001'
$env:PLAYWRIGHT_WEB_BASE='http://localhost:3001'
npx playwright test
```

### Playwright (CI)

GitHub Actions job `playwright-fixture` — ephemeral Postgres, not owner DB.

### Legacy inventory dry-run

```bash
pwsh scripts/local/Cleanup-Owner-TestData.ps1
# or
docker compose exec api python scripts/inventory_legacy_data.py --stdout
```

### Frontend build

```bash
cd apps/web && npm run build
```

### Secret / prohibited source scans

```bash
python scripts/validation/secret_scan.py
python scripts/validation/prohibited_source_scan.py
```

## RC4 validation report checklist (not run until stabilization complete)

- [ ] API SQLite results
- [ ] API PostgreSQL results
- [ ] Migration up/down/up
- [ ] Playwright results
- [ ] Frontend build
- [ ] Secret scan
- [ ] Prohibited source scan
- [ ] Docker health (postgres, api, web)
- [ ] Legacy inventory dry-run reviewed by owner
- [ ] Live connector results (owner reconnect required)

**Do not create tag `r2.13.0-rc4` until this checklist is green and owner approves cleanup dry-run.**
