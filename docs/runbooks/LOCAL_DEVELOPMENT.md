# Local Development Runbook

Windows-first workflow using PowerShell scripts in `scripts/local/`.

## Prerequisites

| Tool | Minimum | Check |
|------|---------|-------|
| Git | any recent | `git --version` |
| Python | 3.12+ | `python --version` |
| Node.js | 20+ | `node --version` |
| npm | bundled with Node | `npm --version` |
| PowerShell | 7+ | `pwsh --version` |
| Docker Desktop | for full stack | `docker --version` and `docker compose version` |

Optional: place Google OAuth client JSON at `C:\AarohanSecrets\google-oauth-client.json` (outside repo).

## One-time bootstrap

```powershell
cd C:\Development\Workspace\aarohan-careeros
pwsh .\scripts\local\Bootstrap-Aarohan.ps1
```

Bootstrap verifies prerequisites, creates `.env.local` from `.env.example` if missing, checks OAuth JSON path, runs secret initialization, creates Python venv, and installs npm dependencies.

Skip Docker check (direct-dev path):

```powershell
pwsh .\scripts\local\Bootstrap-Aarohan.ps1 -SkipDockerCheck
```

## Initialize secrets (once per machine)

```powershell
pwsh .\scripts\local\Initialize-AarohanSecrets.ps1
```

Prompts for required secrets into encrypted vault `AarohanLocal`:

- `APP_SECRET`, `POSTGRES_PASSWORD`, `TOKEN_ENCRYPTION_KEY`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- Optional: Google OAuth IDs, `AI_API_KEY`, `N8N_ENCRYPTION_KEY`, `CAREER_GMAIL_ADDRESS`

Re-prompt a secret: add `-Force`.

## Start / stop / reset

**Start full stack (Docker):**

```powershell
pwsh .\scripts\local\Start-Aarohan.ps1          # foreground, logs attached
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached # background
```

Loads secrets from SecretStore into environment, sets `SCHEDULING_ENABLED=false`, runs `docker compose up --build`.

**Stop:**

```powershell
pwsh .\scripts\local\Stop-Aarohan.ps1
```

**Reset (destructive):**

```powershell
pwsh .\scripts\local\Reset-Aarohan.ps1              # stops containers
pwsh .\scripts\local\Reset-Aarohan.ps1 -Volumes     # also removes DB volumes
pwsh .\scripts\local\Reset-Aarohan.ps1 -Force       # skip confirmation
```

## Validate

```powershell
pwsh .\scripts\local\Test-Aarohan.ps1
```

Runs: secret scan, prohibited-source scan, pytest (API), `npm run build` (web). If stack is running, checks `/health` and `/ready`.

## Docker mode (default)

Services from `docker-compose.yml`:

| Service | Port | Purpose |
|---------|------|---------|
| postgres | 5432 | Database |
| api | 8000 | FastAPI + Alembic migrations on start |
| web | 3000 | Next.js dashboard |
| n8n | 5678 | Workflow UI |

**URLs:**

- Dashboard: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- n8n: http://localhost:5678

First dashboard visit uses admin credentials from SecretStore (or creates admin on first login per bootstrap rules).

**Live Google OAuth:** set `OAUTH_FIXTURE_MODE=false` in environment before start (fixture mode defaults to `true` in compose). Store `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in SecretStore — the Windows JSON path is not visible inside the Linux API container.

## Direct-dev mode (no full Docker)

Use when Docker Desktop is unavailable or for faster API/web iteration.

1. Bootstrap with `-SkipDockerCheck`.
2. Start Postgres only: `docker compose up postgres -d` (or use a local PostgreSQL instance).
3. Load secrets manually (same names as `Start-Aarohan.ps1` sets) and export `DATABASE_URL` pointing to `localhost:5432`.
4. API:

```powershell
cd apps\api
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. Web (separate terminal):

```powershell
cd apps\web
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8000"
npm run dev
```

For direct-dev, `GOOGLE_OAUTH_CLIENT_JSON_PATH=C:\AarohanSecrets\google-oauth-client.json` works because the API runs on Windows.

## Playwright E2E (optional)

Requires running stack:

```powershell
cd apps\web
npx playwright install   # first time only
npm run test:e2e
```

## Related docs

- [Google OAuth](GOOGLE_OAUTH.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Backup & restore](BACKUP_RESTORE.md)
- [Test strategy](../testing/TEST_STRATEGY.md)
