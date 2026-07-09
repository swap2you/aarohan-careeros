# Local application execution runbook

**Canonical guide** for running, testing, and troubleshooting Aarohan CareerOS on Windows.  
**Repository:** `C:\Development\Workspace\aarohan-careeros`  
**Last updated:** 2026-07-01 (local `.env.local` runtime + admin bypass)

---

## Quick reference

| Goal | Command |
|------|---------|
| First-time machine setup | `pwsh .\scripts\local\Bootstrap-Aarohan.ps1` |
| **Sync / fix secrets in `.env.local`** | `pwsh .\scripts\local\Sync-EnvLocal.ps1` |
| Generate missing crypto keys only | `pwsh .\scripts\local\Sync-EnvLocal.ps1 -GenerateMissing` |
| **Start app (Docker)** | `pwsh .\scripts\local\Start-Aarohan.ps1 -Detached` |
| **Stop app** | `pwsh .\scripts\local\Stop-Aarohan.ps1` |
| **Cold restart (test)** | `pwsh .\scripts\local\Restart-Aarohan.ps1` |
| Local admin status | `pwsh .\scripts\local\Show-LocalAdminStatus.ps1` |
| Light validation | `pwsh .\scripts\local\Test-Aarohan.ps1` |
| Full R2 gate | `pwsh .\scripts\validation\Verify-Full-R2.ps1` |
| Live OAuth/Gmail checks | `pwsh .\scripts\validation\Live-RC-Validation.ps1` |
| Backup DB | `pwsh .\scripts\local\Backup-Aarohan.ps1` |
| Restore DB | `pwsh .\scripts\local\Restore-Aarohan.ps1 -BackupFile <path>` |
| Reset admin password | `pwsh .\scripts\local\Reset-LocalAdmin.ps1 -Force -UseConfiguredPassword` |
| E2E stack (isolated DB) | `pwsh .\scripts\local\Start-Aarohan-E2E.ps1 -Detached` |
| Playwright E2E | `cd apps\web; npm run test:e2e` |

**URLs after start:**

| Service | URL |
|---------|-----|
| Dashboard | http://127.0.0.1:3000 |
| Login | http://127.0.0.1:3000/login |
| Settings (Google) | http://127.0.0.1:3000/settings |
| API health | http://127.0.0.1:8000/health |
| API ready | http://127.0.0.1:8000/ready |
| API docs | http://127.0.0.1:8000/docs |
| n8n | http://127.0.0.1:5678 |
| E2E web (isolated) | http://127.0.0.1:3001 |

---

## 0. Exact start sequence (copy/paste)

Run these **in order** from repo root (`C:\Development\Workspace\aarohan-careeros`):

```powershell
cd C:\Development\Workspace\aarohan-careeros

# 1) One-time: tools + npm/pip (skip if already done)
pwsh .\scripts\local\Bootstrap-Aarohan.ps1

# 2) Ensure .env.local has all required secrets (merges from C:\AarohanSecrets\aarohan.local.env if present)
pwsh .\scripts\local\Sync-EnvLocal.ps1

# If step 2 reports missing APP_SECRET / POSTGRES_PASSWORD / TOKEN_ENCRYPTION_KEY:
pwsh .\scripts\local\Sync-EnvLocal.ps1 -GenerateMissing

# 3) Start Docker stack (postgres + api + web)
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached

# 4) Verify (use --env-file so compose sees POSTGRES_PASSWORD)
docker compose --env-file .env.local ps
Invoke-RestMethod http://127.0.0.1:8000/health
```

Open **http://127.0.0.1:3000** — click **Enter Local Admin** (when `LOCAL_DEV_AUTH_BYPASS=true`) or sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env.local`.

**Common error:** `Missing required values in .env.local: APP_SECRET, POSTGRES_PASSWORD, TOKEN_ENCRYPTION_KEY`  
→ Run step 2 again. `Sync-EnvLocal.ps1` copies values from `C:\AarohanSecrets\aarohan.local.env` into repo `.env.local`, or generates crypto keys with `-GenerateMissing`.

### Daily workflow (you do not repeat Section 0 every time)

| Situation | Command |
|-----------|---------|
| App already running | Use http://127.0.0.1:3000 — nothing else |
| After git pull or code/UI changes | `pwsh .\scripts\local\Start-Aarohan.ps1 -Detached` |
| Stack was stopped | `pwsh .\scripts\local\Start-Aarohan.ps1 -Detached` |
| Secrets changed | `pwsh .\scripts\local\Sync-EnvLocal.ps1` then restart |
| Cold restart | `pwsh .\scripts\local\Restart-Aarohan.ps1` |

Plain `docker compose ps` fails without env — use `docker compose --env-file .env.local ps`.

---

## 1. Prerequisites

Verify before bootstrap:

| Tool | Required version | Check command |
|------|------------------|---------------|
| Git | recent | `git --version` |
| Python | **3.12+** | `python --version` |
| Node.js | **20+** | `node --version` |
| npm | bundled with Node | `npm --version` |
| PowerShell | **7+** (`pwsh`) | `pwsh --version` |
| Docker Desktop | for default stack | `docker --version` and `docker compose version` |

**Stack versions (pinned in repo):**

| Component | Version |
|-----------|---------|
| PostgreSQL (Docker) | 16-alpine |
| API runtime (Docker) | Python 3.12-slim |
| Next.js | 15.1.2 |
| React | 19.0.0 |
| Playwright | 1.49.1 |
| n8n | 1.70.3 |

**Outside repo (not in Git):**

| Item | Location |
|------|----------|
| **Primary runtime config (required)** | `.env.local` in repo root (copy from `.env.local.example`) |
| Legacy secrets file (optional merge source) | `C:\AarohanSecrets\aarohan.local.env` |
| Google OAuth client JSON | `C:\AarohanSecrets\google-oauth-client.json` |
| SecretStore vault (optional legacy) | PowerShell vault `AarohanLocal` |

---

## 2. Configuration model

### Single file: `.env.local` (repo root)

All Docker services read **`.env.local`** via `Start-Aarohan.ps1` → `Invoke-AarohanCompose.ps1`.

**Required keys** (must be non-empty):

| Variable | Purpose |
|----------|---------|
| `APP_ENV` | Set to `local` |
| `LOCAL_DEV_AUTH_BYPASS` | Set to `true` for one-click local admin login |
| `APP_SECRET` | Session/crypto secret (32+ chars) |
| `POSTGRES_PASSWORD` | Postgres password for Docker |
| `TOKEN_ENCRYPTION_KEY` | OAuth token encryption key |
| `ADMIN_EMAIL` | Your login email |
| `ADMIN_PASSWORD` | Your login password (12+ chars) |

**Never commit `.env.local`.** It is gitignored.

Create or repair:

```powershell
Copy-Item .env.local.example .env.local   # if missing
pwsh .\scripts\local\Sync-EnvLocal.ps1
```

`Sync-EnvLocal.ps1`:

1. Merges missing required keys from `C:\AarohanSecrets\aarohan.local.env` (legacy)
2. Optionally pulls from SecretStore: `-UseSecretStore`
3. Generates crypto keys only: `-GenerateMissing`

### Optional non-secrets in `.env.local`

```env
OAUTH_FIXTURE_MODE=false
CAREER_GMAIL_ADDRESS=your-career@gmail.com
GOOGLE_DRIVE_ROOT_FOLDER_ID=<your-drive-root-id>
GOOGLE_OAUTH_CLIENT_JSON_PATH=C:\AarohanSecrets\google-oauth-client.json
ENABLE_EXTERNAL_EMAIL_SEND=false
# Connector keys: ADZUNA_*, JOOBLE_*, USAJOBS_*, OPENAI_API_KEY / AI_API_KEY
```

### Legacy SecretStore (optional)

If you still use PowerShell SecretStore:

```powershell
pwsh .\scripts\local\Sync-EnvLocal.ps1 -UseSecretStore -GenerateMissing
# or start with vault directly:
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached -UseSecretStore
```

---

## 3. One-time bootstrap

```powershell
cd C:\Development\Workspace\aarohan-careeros
pwsh .\scripts\local\Bootstrap-Aarohan.ps1
```

Bootstrap:

1. Verifies Git, Python 3.12+, Node 20+, npm, pwsh, Docker (warns if missing)
2. Creates `.env.local` from `.env.local.example` if absent
3. Warns if OAuth JSON path missing
4. Creates `apps/api/.venv` and installs Python deps
5. Runs `npm install` in `apps/web`

Then run:

```powershell
pwsh .\scripts\local\Sync-EnvLocal.ps1
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached
```

Skip Docker check (direct-dev path only):

```powershell
pwsh .\scripts\local\Bootstrap-Aarohan.ps1 -SkipDockerCheck
```

---

## 4. Start the application (default: Docker)

### Start

```powershell
pwsh .\scripts\local\Start-Aarohan.ps1          # foreground, logs attached
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached # background
```

`Start-Aarohan.ps1`:

- Runs `Sync-EnvLocal.ps1` (ensures `.env.local` is complete)
- Loads `.env.local` and passes it to `docker compose --env-file .env.local`
- Binds services to **127.0.0.1** (3000, 8000, 5432)
- Sets `SCHEDULING_ENABLED=false`, `ENABLE_EXTERNAL_EMAIL_SEND=false` when unset
- Bind-mounts `C:\AarohanSecrets` → `/run/secrets` in API container (OAuth JSON)
- Runs `docker compose up --build`

### Confirm healthy

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

All services should show `healthy` within ~1–2 minutes on first build.

### Stop

```powershell
pwsh .\scripts\local\Stop-Aarohan.ps1
```

Equivalent: `docker compose down` (preserves volumes).

### Restart without losing data

```powershell
docker compose restart api web
# or full stack:
docker compose down
docker compose up -d
```

**Never** use `docker compose down -v` unless you intend to wipe Postgres.

---

## 4b. Stop and cold restart (testing)

Use this when you want to prove the app survives a **full stop and start** (session persistence, Google tokens, database data) without wiping volumes.

### What is preserved vs stopped

| Preserved (`docker compose down`) | Stopped |
|-----------------------------------|---------|
| PostgreSQL data (jobs, users, OAuth tokens, sessions) | API, web, n8n, postgres **containers** |
| Docker volumes `postgres_data`, `generated_docs`, `n8n_data` | In-memory API state |
| Your login users in the database | Browser tab may show stale UI until refresh |

**Not preserved** if you run `Reset-Aarohan.ps1 -Volumes` or `docker compose down -v`.

### Standard cold restart (recommended)

From repo root. **No SecretStore unlock required** when using `.env.local`.

```powershell
cd C:\Development\Workspace\aarohan-careeros

# One command: stop all containers, then start with .env.local
pwsh .\scripts\local\Restart-Aarohan.ps1
```

Or step by step:

```powershell
# 1. Stop every service (api, web, postgres, n8n)
pwsh .\scripts\local\Stop-Aarohan.ps1

# 2. Confirm nothing is running (optional)
docker compose ps

# 3. Start again (syncs .env.local, rebuilds if needed)
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached

# 4. Wait ~30–90s on first build, then verify
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

### Post-restart smoke test

```powershell
# API login (owner) — should return 200 without re-setup
# Load password from docs/runbooks/LOCAL-CREDENTIALS.private.md (gitignored).
$loginPassword = $env:OWNER_LOGIN_PASSWORD  # set locally; never commit
$login = @{
  email = "swapnilpatil.tech@gmail.com"
  password = $loginPassword
  remember_me = $true
} | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/auth/login `
  -ContentType "application/json" -Body $login

# Browser: open fresh tab
start http://localhost:3000/login
```

Expected after restart:

- Login works with owner credentials (see `LOCAL-CREDENTIALS.private.md`)
- Remember Me session may require sign-in again in browser after long stop (cookie still valid if within expiry)
- Google integration stays **READY** if `OAUTH_FIXTURE_MODE=false` and OAuth was connected before (no new consent)
- Data (jobs, applications) still present in dashboard

### Restart only API + web (faster, keeps postgres connection pool warm)

```powershell
docker compose restart api web
```

Use full cold restart above when testing Docker-down / Docker-up persistence.

### Wipe everything and start from scratch (destructive)

Only when you intentionally want an empty database:

```powershell
pwsh .\scripts\local\Stop-Aarohan.ps1
docker compose down -v          # DESTROYS postgres + n8n + generated volumes
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached
pwsh .\scripts\local\Reset-LocalAdmin.ps1 -Force -Email swapnilpatil.tech@gmail.com
pwsh .\scripts\local\Ensure-E2ETestUser.ps1
```

Then sign in again and reconnect Google in Settings.

---

## 5. Sign in

Authentication uses **HttpOnly cookie** `careeros_session` (R2.6.1+), not browser `localStorage`.

### Login accounts (this machine)

Full usernames and passwords: **`docs/runbooks/LOCAL-CREDENTIALS.private.md`** (gitignored — not pushed to GitHub).

| Account | Email | Use |
|---------|-------|-----|
| **Owner (daily)** | `swapnilpatil.tech@gmail.com` | Dashboard, Settings, Google OAuth, real workflow |
| **E2E / Playwright** | `e2e@test.local` | Automated tests only (`E2eTestPass123!`) |

`e2e@test.local` fails with "Invalid credentials" until you create that user (owner admin already exists from first setup).

### First-time or forgot password

**Owner admin** (sets your Gmail login; removes other users — run E2E script after):

```powershell
$env:RESET_LOCAL_ADMIN_PASSWORD = Read-Host "New admin password" -AsSecureString
pwsh .\scripts\local\Reset-LocalAdmin.ps1 -Force -Email swapnilpatil.tech@gmail.com
Remove-Item Env:RESET_LOCAL_ADMIN_PASSWORD
```

**E2E user** (keeps owner admin):

```powershell
pwsh .\scripts\local\Ensure-E2ETestUser.ps1
```

### Other cases

| Account | When to use |
|---------|-------------|
| SecretStore `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Must match owner row after `Start-Aarohan.ps1` |
| First-run setup form | Only if no admin exists (`/api/auth/setup-status` → `setup_required: true`) |

Reset admin to match SecretStore:

```powershell
pwsh .\scripts\local\Reset-LocalAdmin.ps1
```

Open http://localhost:3000/login → sign in → Executive Overview should load. Protected routes redirect to login when session expires.

**Why `e2e@test.local` failed:** That user is not created automatically when a real admin already exists. Use the owner email above for daily login, or run `Ensure-E2ETestUser.ps1` for Playwright.

---

## 6. Google OAuth and Drive (live)

1. Set `OAUTH_FIXTURE_MODE=false` (see §2).
2. Place OAuth JSON at `C:\AarohanSecrets\google-oauth-client.json`.
3. Start stack via `Start-Aarohan.ps1`.
4. Open http://localhost:3000/settings → **Connect Google**.
5. Approve Drive + Gmail readonly scopes.
6. If Drive root inaccessible: **Create Aarohan Drive Root** → **Sync Drive Subfolders**.

Detail: [GOOGLE_OAUTH.md](GOOGLE_OAUTH.md)

---

## 7. Test the application

### Layer 1 — Quick local validation

```powershell
pwsh .\scripts\local\Test-Aarohan.ps1
```

Runs: secret scan, prohibited-source scan, API pytest (SQLite), web `npm run build`, optional `/health` + `/ready` if stack is up.

### Layer 2 — Full R2 release gate

```powershell
pwsh .\scripts\validation\Verify-Full-R2.ps1
```

Runs: clean tree check, tag audit, scans, pytest, web build, **Playwright (19 tests)**, Docker health.  
Report: `generated/validation-reports/verify-full-r2-<timestamp>.txt`

Skip options:

```powershell
pwsh .\scripts\validation\Verify-Full-R2.ps1 -SkipDocker
pwsh .\scripts\validation\Verify-Full-R2.ps1 -SkipPlaywright
```

### Layer 3 — PostgreSQL integration tests (Docker)

Local pytest skips 8 tests without PostgreSQL. **Never run these against the owner
`career_os` database** — they reset the public schema. Use the isolated E2E DB:

```powershell
# Ensure career_os_e2e exists (Start-Aarohan-E2E.ps1 creates it)
docker compose exec -T postgres psql -U career_os -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='career_os_e2e'" | findstr 1
if ($LASTEXITCODE -ne 0) {
  docker compose exec -T postgres psql -U career_os -d postgres -c "CREATE DATABASE career_os_e2e OWNER career_os;"
}

docker compose exec -T `
  -e DATABASE_URL=postgresql+psycopg://career_os:${env:POSTGRES_PASSWORD}@postgres:5432/career_os_e2e `
  api pytest tests/test_migrations.py tests/test_duplicate_risk_postgres.py -q
```

Schema-reset helpers refuse `career_os` unless the URL is the CI ephemeral
`testpass` service database.

**Do not** run `docker compose exec -T api pytest tests/test_migrations.py
tests/test_duplicate_risk_postgres.py` against the owner API container — that
container’s `DATABASE_URL` points at owner `career_os` and will wipe it.

### Layer 4 — Playwright E2E

Requires running stack. First time:

```powershell
cd apps\web
npx playwright install chromium
npm run test:e2e
```

Reports: `artifacts/playwright/` (gitignored).

**Note:** Playwright creates `e2e@test.local` only when `setup_required` is true. If a real admin already exists, some auth tests may fail until you use a test database or dedicated e2e environment.

### Layer 5 — Live validation (owner)

After `Start-Aarohan.ps1` with live OAuth:

```powershell
pwsh .\scripts\validation\Live-RC-Validation.ps1
```

Redacted report: `generated/validation-reports/live-rc-<timestamp>.json`

### Layer 6 — API smoke inside container

```powershell
docker compose exec -T api python scripts/live_rc_validation.py
```

### Layer 7 — Manual UAT

Cowork checklist: `docs/validation/uat/COWORK-UAT-PACKAGE.md`

---

## 8. Script inventory

### `scripts/local/`

| Script | Purpose |
|--------|---------|
| `Bootstrap-Aarohan.ps1` | One-time machine setup |
| `Initialize-AarohanSecrets.ps1` | SecretStore vault setup |
| `Start-Aarohan.ps1` | Start Docker stack (SecretStore + `.env.local`) |
| `Stop-Aarohan.ps1` | Stop all containers (`docker compose down`) |
| `Restart-Aarohan.ps1` | Stop + cold start (keeps volumes) |
| `Reset-Aarohan.ps1` | Stop; optional `-Volumes` wipe |
| `Test-Aarohan.ps1` | Light validation |
| `Backup-Aarohan.ps1` | Postgres dump to `artifacts/backups/` |
| `Restore-Aarohan.ps1` | Restore from SQL file |
| `Reset-LocalAdmin.ps1` | Align admin user with SecretStore |
| `Ensure-E2ETestUser.ps1` | Add Playwright `e2e@test.local` without removing owner |

### `scripts/validation/`

| Script | Purpose |
|--------|---------|
| `Verify-Full-R2.ps1` | Canonical full gate |
| `Verify-R2-Release-Gate.ps1` | Lighter gate (no Playwright by default in some configs) |
| `Live-RC-Validation.ps1` | Live API checks (redacted) |
| `secret_scan.py` | Detect committed secrets |
| `prohibited_source_scan.py` | Policy scan (no LinkedIn/Indeed scrape) |

### `apps/api/scripts/`

| Script | Purpose |
|--------|---------|
| `live_rc_validation.py` | In-container live checks |
| `local_smoke.py` | SQLite-only smoke (no Docker) |

---

## 9. Direct-dev mode (no full Docker)

When Docker Desktop is unavailable or for faster API iteration:

1. `Bootstrap-Aarohan.ps1 -SkipDockerCheck`
2. Postgres only: `docker compose up postgres -d`
3. Export secrets (same names as `Start-Aarohan.ps1`)
4. API:

```powershell
cd apps\api
.\.venv\Scripts\activate
$env:DATABASE_URL = "postgresql+psycopg://career_os:<POSTGRES_PASSWORD>@localhost:5432/career_os"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. Web (separate terminal):

```powershell
cd apps\web
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8000"
npm run dev
```

Direct-dev can read `GOOGLE_OAUTH_CLIENT_JSON_PATH` as a Windows path.

---

## 10. Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for full detail. Common issues:

| Symptom | Fix |
|---------|-----|
| `Missing required secret` on start | `Initialize-AarohanSecrets.ps1` |
| `POSTGRES_PASSWORD required` on bare compose | Always use `Start-Aarohan.ps1` or export secrets first |
| API crash loop / `relation already exists` | `docker compose run --rm api alembic stamp head` then `docker compose up -d api` |
| Login works but dashboard empty / 401 | Use SecretStore admin; check cookie not blocked; restart API |
| Google shows fixture behavior | Export `OAUTH_FIXTURE_MODE=false` before start |
| Playwright auth failures | Real admin DB vs `e2e@test.local` — see §7 Layer 4 |
| Port in use | `netstat -ano \| findstr :8000` |

Logs:

```powershell
docker compose logs -f api
docker compose logs -f web
```

---

## 11. Backup and restore

```powershell
pwsh .\scripts\local\Backup-Aarohan.ps1
pwsh .\scripts\local\Restore-Aarohan.ps1 -BackupFile artifacts\backups\<file>.sql
```

Detail: [BACKUP_RESTORE.md](BACKUP_RESTORE.md)

---

## 12. Related documentation

| Doc | Purpose |
|-----|---------|
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Error catalog |
| [GOOGLE_OAUTH.md](GOOGLE_OAUTH.md) | OAuth scopes and callbacks |
| [BACKUP_RESTORE.md](BACKUP_RESTORE.md) | Database backup |
| `docs/00-CURRENT-STATUS.md` | Program phase and RC status |
| `docs/validation/RC-BASELINE-VERIFICATION.md` | Test counts and skipped tests |
| `docs/testing/TEST_STRATEGY.md` | Test philosophy |
| `docs/11_LOCAL_FIRST_SECRET_STRATEGY.md` | Secret handling policy |

---

## 13. Daily owner workflow (summary)

```powershell
cd C:\Development\Workspace\aarohan-careeros

# Start
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached

# ... use app at http://localhost:3000 ...

# Cold restart test (stop + start, keep data)
pwsh .\scripts\local\Restart-Aarohan.ps1

# Stop when done
pwsh .\scripts\local\Stop-Aarohan.ps1
```
