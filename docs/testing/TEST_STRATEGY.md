# Test Strategy

Layered validation for Aarohan CareerOS. All behavior changes should include tests per `AGENTS.md`.

## Layers

| Layer | Tool | Scope | When |
|-------|------|-------|------|
| Unit / API | pytest | Business logic, OAuth, migrations | Every change; CI |
| Repository scans | Python scripts | Secrets, prohibited sources | Local + CI |
| Frontend build | `npm run build` | TypeScript compile, Next.js bundle | Local + CI |
| E2E | Playwright | Dashboard smoke | Manual / pre-release |
| UAT | Manual + Cowork | Full user journeys | Pre-release |

## Backend (pytest)

**Location:** `apps/api/tests/`

| File | Coverage |
|------|----------|
| `test_core.py` | Scoring, ingestion, approvals, AI caps |
| `test_oauth.py` | OAuth URL building, token handling |
| `test_google_integration.py` | Gmail/Drive with fixtures |
| `test_migrations.py` | Alembic head consistency |

**Run locally:**

```powershell
cd apps\api
.\.venv\Scripts\pytest -q          # quiet
.\.venv\Scripts\pytest -v          # verbose
.\.venv\Scripts\pytest tests/test_oauth.py -v   # single file
```

**Fixtures:** CI sets `OAUTH_FIXTURE_MODE=true` — no live Google credentials required.

**Database:** Tests use test DB URL from `conftest.py` / env. CI spins Postgres 16 service container.

## Repository scans

**Location:** `scripts/validation/`

| Script | Purpose |
|--------|---------|
| `secret_scan.py` | Detects PATs, private keys, hardcoded passwords |
| `prohibited_source_scan.py` | Blocks LinkedIn/Indeed scraping patterns |

**Run:**

```powershell
python scripts/validation/secret_scan.py
python scripts/validation/prohibited_source_scan.py
```

Both run inside `Test-Aarohan.ps1`.

## Frontend build

```powershell
cd apps\web
npm run build
```

Validates TypeScript, Next.js 15 production build, and static generation. Lint: `npm run lint`.

## Playwright E2E

**Location:** `apps/web/tests/e2e/`

**Config:** `apps/web/playwright.config.ts` — base URL `http://localhost:3000`, 30s timeout.

**Current coverage:** `smoke.spec.ts` — dashboard login shell renders.

**Run (stack must be up):**

```powershell
cd apps\web
npx playwright install    # first run
npm run test:e2e
```

Expand E2E before release gates (`docs/09_RELEASE_GATES.md`).

## Local validation script

Single entry point:

```powershell
pwsh .\scripts\local\Test-Aarohan.ps1
```

Order: secret scan → prohibited scan → pytest → web build → health endpoints (if running).

## CI (GitHub Actions)

**Workflow:** `.github/workflows/ci.yml`

Triggers: push/PR to `main` or `master`.

| Job | Steps |
|-----|-------|
| `api-tests` | Python 3.12, Postgres 16 service, `pytest -q` |
| `validation-scans` | Both scan scripts |
| `web-build` | Node 20, `npm install`, `npm run build` |

CI env uses disposable secrets (`APP_SECRET`, `TOKEN_ENCRYPTION_KEY`, `OAUTH_FIXTURE_MODE=true`). No personal Gmail or production keys.

Playwright is **not** in CI yet — run locally before signoff.

## Test data

- **Fixtures:** API fixture mode for Gmail/Drive (`OAUTH_FIXTURE_MODE=true`).
- **Career Vault:** `career_vault/` — use only approved evidence in generation tests.
- **No fabrication:** Tests must not assert unverified professional claims.

## Release test checklist

From `docs/09_RELEASE_GATES.md`:

- [ ] pytest green
- [ ] Scans green
- [ ] Web build green
- [ ] Playwright smoke (expand as coverage grows)
- [ ] Backup + restore drill
- [ ] `/health` and `/ready` green
- [ ] Cowork UAT PASS — see [UAT_RUNBOOK.md](UAT_RUNBOOK.md)

## Adding tests

1. Prefer unit tests over E2E for business logic.
2. Mock external APIs; never call live Google in CI.
3. Use existing `conftest.py` fixtures and patterns in sibling test files.
4. Run full `Test-Aarohan.ps1` before claiming success.
