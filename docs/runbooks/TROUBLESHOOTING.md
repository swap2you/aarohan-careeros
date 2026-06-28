# Troubleshooting

Common local development issues and fixes. Check logs with `docker compose logs -f api` (or `web`, `postgres`, `n8n`).

## Startup failures

### Missing required secret

**Symptom:** `Start-Aarohan.ps1` throws `Missing required secret 'APP_SECRET'`.

**Fix:** Run `pwsh .\scripts\local\Initialize-AarohanSecrets.ps1`. Required: `APP_SECRET`, `POSTGRES_PASSWORD`, `TOKEN_ENCRYPTION_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.

### POSTGRES_PASSWORD / APP_SECRET required (compose)

**Symptom:** Docker compose exits with `POSTGRES_PASSWORD required`.

**Fix:** Always start via `Start-Aarohan.ps1` (loads SecretStore into env). Do not run bare `docker compose up` without exported variables.

### Port already in use

**Symptom:** Bind error on 3000, 8000, 5432, or 5678.

**Fix:** Stop conflicting services or change host ports in `docker-compose.yml`. Find process: `netstat -ano | findstr :8000`.

### API not ready / migrations fail

**Symptom:** `/ready` returns `not_ready`; API container restarts.

**Fix:**

1. Confirm postgres healthy: `docker compose ps`.
2. Check API logs for Alembic errors.
3. Reset DB if corrupted: `Reset-Aarohan.ps1 -Volumes` (destroys data), then restart.

## Authentication

### Cannot sign in to dashboard

**Fix:**

1. Confirm `ADMIN_EMAIL` / `ADMIN_PASSWORD` in SecretStore match what you enter.
2. Clear browser cookies for localhost:3000.
3. If DB was reset, admin is re-bootstrapped on API start from env secrets.

### CORS errors in browser

**Symptom:** API calls blocked from frontend.

**Fix:** Use http://localhost:3000 (not 127.0.0.1) unless `CORS_ORIGINS` includes both. Default allows `http://localhost:3000`.

## Google OAuth

### Connect button says not configured

**Fix (Docker):** Store `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in SecretStore. Container cannot read `C:\AarohanSecrets\...` directly.

**Fix (direct-dev):** Set `GOOGLE_OAUTH_CLIENT_JSON_PATH` to the JSON file; API loads credentials on startup.

### redirect_uri_mismatch

**Fix:** Add exact callback URIs in Google Cloud Console. See [GOOGLE_OAUTH.md](GOOGLE_OAUTH.md).

### Wrong account connected

**Fix:** Disconnect in Settings; reconnect as `swapnilpatil.tech@gmail.com`.

### Fixture vs live confusion

**Symptom:** Gmail/Drive actions succeed but no real Google data changes.

**Fix:** Set `OAUTH_FIXTURE_MODE=false` before starting stack.

## Tests and validation

### pytest failures

```powershell
cd apps\api
.\.venv\Scripts\pytest -v
```

Ensure venv exists (`Bootstrap-Aarohan.ps1`). CI uses disposable Postgres with test env vars — local failures may indicate missing `DATABASE_URL`.

### Secret scan failures

**Symptom:** `secret_scan.py` reports violations.

**Fix:** Remove credentials from tracked files. Move secrets to SecretStore or `private/`. Never commit `google-oauth-client.json`.

### Frontend build fails

```powershell
cd apps\web
npm install
npm run build
```

Check Node 20+ and TypeScript errors in output.

### Test-Aarohan health check skipped

**Symptom:** "Stack not running or not ready yet."

**Fix:** Expected if stack is stopped. Start with `Start-Aarohan.ps1 -Detached`, wait for healthy containers, re-run tests.

## Docker-specific

### Slow first build

**Fix:** Normal — API image installs system libs for PDF generation. Subsequent builds use cache.

### n8n encryption key warning

**Symptom:** Ephemeral `N8N_ENCRYPTION_KEY` generated each session.

**Fix:** Store a stable key via `Initialize-AarohanSecrets.ps1` to persist n8n credentials across restarts.

### Volume / stale data

**Fix:** `Reset-Aarohan.ps1 -Volumes` wipes postgres and n8n volumes. Back up first — see [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

## Database backup/restore

**Symptom:** Backup produces empty file or restore fails.

**Fix:** Stack must be running. Use scripts documented in [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

## Getting help

1. API docs: http://localhost:8000/docs
2. Audit log in dashboard (Ops section)
3. Validation artifacts in `validation/`
4. Architecture: `docs/architecture/ARCHITECTURE.md`
