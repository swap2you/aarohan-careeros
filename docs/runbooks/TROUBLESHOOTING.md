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

**Symptom:** `/ready` returns `not_ready`; API container restarts; logs show `relation "users" already exists`.

**Fix:**

1. Confirm postgres healthy: `docker compose ps`.
2. Check API logs: `docker compose logs api --tail 50`.
3. If schema exists but `alembic_version` is missing (common after manual DB creation):
   ```powershell
   docker compose run --rm api alembic stamp head
   docker compose up -d api
   ```
4. Corrupted DB only: `Reset-Aarohan.ps1 -Volumes` (destroys data), then restart.

## Authentication

### Cannot sign in to dashboard

**Fix:**

1. Use **SecretStore** credentials: run `Initialize-AarohanSecrets.ps1` if missing; login with `ADMIN_EMAIL` / `ADMIN_PASSWORD` at http://localhost:3000/login
2. Reset admin to match vault: `pwsh .\scripts\local\Reset-LocalAdmin.ps1`
3. Do **not** use `admin@test.local` or Playwright `e2e@test.local` for daily use — those are test-only
4. If session expired: you will redirect to `/login?reason=session_expired` — sign in again
5. Auth uses **HttpOnly cookie** `careeros_session` (R2.6.1+). No token in `localStorage`

### Settings or API returns 401 after Docker restart

**Cause:** Stack started without `Start-Aarohan.ps1` (no `ADMIN_EMAIL` in API container) or stale browser tab.

**Fix:**

1. Always start via `pwsh .\scripts\local\Start-Aarohan.ps1 -Detached`
2. Sign out and sign in again at `/login`
3. Confirm `GET http://localhost:8000/api/auth/session` returns 200 when logged in

### Settings shows "Not authenticated"

**Fix:** Open http://localhost:3000/login first, sign in, then http://localhost:3000/settings. Protected routes require valid session cookie.

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

### Drive root inaccessible after OAuth

**Symptom:** Callback or Settings warns that configured root `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr` is inaccessible.

**Cause:** `drive.file` scope cannot access manually created folders by ID.

**Fix:** Settings → **Create Aarohan Drive Root** → **Sync Drive Subfolders**. Active proven root: `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr`.

### Fixture vs live confusion

**Symptom:** Gmail/Drive actions succeed but no real Google data changes.

**Fix:** Set `OAUTH_FIXTURE_MODE=false` in `.env.local`, **export it into the shell** (or use `docker compose --env-file .env.local`), then restart via `Start-Aarohan.ps1`. Default when unset is `true` in `docker-compose.yml`.

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

### Playwright failures after real admin exists

**Symptom:** Tests timeout at "Executive Overview" using `e2e@test.local`.

**Cause:** Playwright only creates e2e admin when `setup_required` is true; production admin DB skips that path.

**Fix:** Run against fresh test DB, or document as known env limitation. See `docs/runbooks/LOCAL-APPLICATION-EXECUTION.md` §7.

### Verify-Full-R2.ps1 pytest false failure

**Symptom:** Gate fails on pytest stderr warnings despite tests passing.

**Fix:** Use latest `scripts/validation/Verify-Full-R2.ps1` (checks exit code only). Or run `cd apps\api; .\.venv\Scripts\pytest -q` directly.

## Docker-specific

### Slow first build

**Fix:** Normal — API image installs system libs for PDF generation. Subsequent builds use cache.

### n8n encryption key warning

**Symptom:** Ephemeral `N8N_ENCRYPTION_KEY` generated each session.

**Fix:** Store a stable key via `Initialize-AarohanSecrets.ps1` to persist n8n credentials across restarts.

### Volume / stale data

**Fix:** `Reset-Aarohan.ps1 -Volumes` wipes postgres and n8n volumes. Back up first — see [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

### Backup/restore duplicate-object errors

**Symptom:** Restore logs many "already exists" errors for `n8n` schema.

**Fix:** Expected when restoring full-database dump over running DB. Career OS rows restore correctly; use career-only dump for clean restore (known gap).

## Database backup/restore

**Symptom:** Backup produces empty file or restore fails.

**Fix:** Stack must be running. Use scripts documented in [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

## Getting help

1. **Canonical runbook:** `docs/runbooks/LOCAL-APPLICATION-EXECUTION.md`
2. API docs: http://localhost:8000/docs
3. Audit log in dashboard
4. Validation reports: `generated/validation-reports/`
5. Architecture: `docs/architecture/ARCHITECTURE.md`
