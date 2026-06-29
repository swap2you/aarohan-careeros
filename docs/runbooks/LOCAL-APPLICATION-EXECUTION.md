# Local application execution runbook

**Canonical guide** for running, testing, and troubleshooting Aarohan CareerOS on Windows.  
**Repository:** `C:\Development\Workspace\aarohan-careeros`  
**Last updated:** 2026-06-29 (R2.13 RC validation phase)

---

## Quick reference

| Goal | Command |
|------|---------|
| First-time machine setup | `pwsh .\scripts\local\Bootstrap-Aarohan.ps1` |
| Initialize secrets (once) | `pwsh .\scripts\local\Initialize-AarohanSecrets.ps1` |
| **Start app (Docker)** | `pwsh .\scripts\local\Start-Aarohan.ps1 -Detached` |
| **Stop app** | `pwsh .\scripts\local\Stop-Aarohan.ps1` |
| **Cold restart (test)** | `pwsh .\scripts\local\Restart-Aarohan.ps1` |
| Light validation | `pwsh .\scripts\local\Test-Aarohan.ps1` |
| Full R2 gate | `pwsh .\scripts\validation\Verify-Full-R2.ps1` |
| Live OAuth/Gmail checks | `pwsh .\scripts\validation\Live-RC-Validation.ps1` |
| Backup DB | `pwsh .\scripts\local\Backup-Aarohan.ps1` |
| Restore DB | `pwsh .\scripts\local\Restore-Aarohan.ps1 -BackupFile <path>` |
| Reset admin password | `pwsh .\scripts\local\Reset-LocalAdmin.ps1` |
| Ensure E2E test user | `pwsh .\scripts\local\Ensure-E2ETestUser.ps1` |
| Playwright E2E | `cd apps\web; npm run test:e2e` |

**URLs after start:**

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| Login | http://localhost:3000/login |
| Settings (Google) | http://localhost:3000/settings |
| API health | http://localhost:8000/health |
| API ready | http://localhost:8000/ready |
| API docs | http://localhost:8000/docs |
| n8n | http://localhost:5678 |

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
| Secret vault | PowerShell SecretStore vault `AarohanLocal` |
| Google OAuth client JSON | `C:\AarohanSecrets\google-oauth-client.json` |
| Non-secret local config | `.env.local` (gitignored, copy from `.env.example`) |

---

## 2. Configuration model

### Secrets → SecretStore only

Never put these in `.env.local`, Git, or Cursor chat:

- `APP_SECRET`, `POSTGRES_PASSWORD`, `TOKEN_ENCRYPTION_KEY`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (optional if JSON file used)
- `AI_API_KEY`, `N8N_ENCRYPTION_KEY`

Initialize:

```powershell
cd C:\Development\Workspace\aarohan-careeros
pwsh .\scripts\local\Initialize-AarohanSecrets.ps1
```

Re-prompt a value: add `-Force`.

### Non-secrets → `.env.local`

Copy template:

```powershell
Copy-Item .env.example .env.local   # if missing
```

Typical `.env.local` entries (no secret values):

```env
OAUTH_FIXTURE_MODE=false
CAREER_GMAIL_ADDRESS=your-career@gmail.com
GOOGLE_DRIVE_ROOT_FOLDER_ID=<your-drive-root-id>
GOOGLE_OAUTH_CLIENT_JSON_PATH=C:\AarohanSecrets\google-oauth-client.json
ENABLE_EXTERNAL_EMAIL_SEND=false
# Optional connector keys: ADZUNA_*, JOOBLE_*, USAJOBS_*, RSS_FEED_URLS
```

**Important:** `Start-Aarohan.ps1` loads **SecretStore** into the shell environment but does **not** automatically read `.env.local`. For live Google and connector keys in `.env.local`, either:

**Option A — export before start (recommended for live mode):**

```powershell
# Load non-secrets from .env.local into current session
Get-Content .env.local | Where-Object { $_ -match '^\s*[^#]' -and $_ -match '=' } | ForEach-Object {
    $n, $v = $_ -split '=', 2
    Set-Item -Path "env:$($n.Trim())" -Value $v.Trim()
}
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached
```

**Option B — compose env file (after exporting secrets via Start-Aarohan pattern):**

```powershell
# After SecretStore vars are in $env:, also pass .env.local to compose:
docker compose --env-file .env.local up --build -d
```

If `OAUTH_FIXTURE_MODE` is unset, Docker defaults to **`true`** (fixture Gmail/Drive).

---

## 3. One-time bootstrap

```powershell
cd C:\Development\Workspace\aarohan-careeros
pwsh .\scripts\local\Bootstrap-Aarohan.ps1
```

Bootstrap:

1. Verifies Git, Python 3.12+, Node 20+, npm, pwsh, Docker (warns if missing)
2. Creates `.env.local` from `.env.example` if absent
3. Warns if OAuth JSON path missing
4. Runs `Initialize-AarohanSecrets.ps1`
5. Creates `apps/api/.venv` and installs Python deps
6. Runs `npm install` in `apps/web`

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

- Loads required secrets from SecretStore
- Sets `SCHEDULING_ENABLED=false`, `ENABLE_EXTERNAL_EMAIL_SEND=false`
- Bind-mounts `C:\AarohanSecrets` → `/run/secrets` in API container
- Runs `docker compose up --build`

### Confirm healthy

```powershell
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
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

From repo root. **Unlock your SecretStore vault** when `Start-Aarohan.ps1` prompts (required for `APP_SECRET`, `POSTGRES_PASSWORD`, etc.).

```powershell
cd C:\Development\Workspace\aarohan-careeros

# One command: stop all containers, then start with secrets + .env.local
pwsh .\scripts\local\Restart-Aarohan.ps1
```

Or step by step:

```powershell
# 1. Stop every service (api, web, postgres, n8n)
pwsh .\scripts\local\Stop-Aarohan.ps1

# 2. Confirm nothing is running (optional)
docker compose ps

# 3. Start again (loads SecretStore + .env.local, rebuilds if needed)
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached

# 4. Wait ~30–90s on first build, then verify
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
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

Local pytest skips 8 tests without PostgreSQL. Run in container:

```powershell
docker compose exec -T api pytest tests/test_migrations.py tests/test_duplicate_risk_postgres.py -q
```

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
