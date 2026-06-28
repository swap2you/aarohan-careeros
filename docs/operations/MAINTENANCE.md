# Operations and Maintenance

Local-first maintenance guide. Production VPS procedures are deferred until deployment.

## Schedules (disabled locally)

Local stack explicitly disables automated scheduling:

| Setting | Local value | Effect |
|---------|-------------|--------|
| `SCHEDULING_ENABLED` | `false` (set by `Start-Aarohan.ps1`) | No cron-style job runs in API |
| `enable_scheduled_workflows` | `false` (config default) | Workflow triggers idle |
| n8n schedules | Manual only | Workflows do not auto-fire unless enabled in n8n UI |

**Why:** Local-first mode prioritizes supervised, on-demand operation. Re-enable only on a deployed VPS with monitoring and approval gates reviewed.

To test a workflow manually: n8n UI at http://localhost:5678 or API workflow endpoints (authenticated).

## Secret rotation

Rotate after exposure, team change, or pre-production promotion.

| Secret | Rotation procedure |
|--------|-------------------|
| `APP_SECRET` | Generate new 32+ char value → SecretStore → restart stack → users re-login |
| `POSTGRES_PASSWORD` | New password in SecretStore → `Backup-Aarohan.ps1` → update postgres env → restore or `ALTER USER` |
| `TOKEN_ENCRYPTION_KEY` | **Destructive for OAuth tokens** — disconnect Google, rotate key, reconnect OAuth |
| `ADMIN_PASSWORD` | SecretStore → restart API → use new password |
| Google OAuth client | Regenerate in Cloud Console → update JSON at `C:\AarohanSecrets\` and SecretStore → reconnect |
| Google refresh tokens | Disconnect in Settings → revoke at myaccount.google.com → reconnect |
| `AI_API_KEY` | Rotate at provider → SecretStore → restart API |
| `N8N_ENCRYPTION_KEY` | Stable value in SecretStore; changing it invalidates stored n8n credentials |

**Never** commit rotated values to Git. Update SecretStore with `-Force`:

```powershell
pwsh .\scripts\local\Initialize-AarohanSecrets.ps1 -Force
```

Document rotation date in personal ops notes (not in repo).

## Dependency updates

### Python (API)

```powershell
cd apps\api
.\.venv\Scripts\pip install -r requirements.txt --upgrade
.\.venv\Scripts\pytest -q
```

Pin versions in `requirements.txt` after testing.

### Node (web)

```powershell
cd apps\web
npm update
npm run build
npm run test:e2e   # if stack running
```

### Docker images

```powershell
docker compose pull
docker compose build --no-cache
pwsh .\scripts\local\Test-Aarohan.ps1
```

Postgres: `postgres:16-alpine`. n8n: pinned to `1.70.3` in compose — upgrade deliberately after reading n8n release notes.

### Database migrations

Alembic runs on API startup. After pulling new code:

1. `Backup-Aarohan.ps1`
2. `Start-Aarohan.ps1 -Detached`
3. Verify `/ready` and spot-check dashboard

## Backups

See `docs/runbooks/BACKUP_RESTORE.md`. Minimum: backup before reset, migration, or weekly during active use.

## Health monitoring (local)

| Check | URL / command |
|-------|---------------|
| API liveness | http://localhost:8000/health |
| API + DB | http://localhost:8000/ready |
| Container status | `docker compose ps` |
| Logs | `docker compose logs -f api web` |

No external uptime monitor in local mode.

## AI budget

Configured in API settings (`config.py`):

- Soft cap: $75/month
- Hard cap: $150/month
- Per job packet: $3
- Per interview pack: $8

Review spend on Ops dashboard. Hard cap blocks further AI calls until next period or manual override in config.

## Security maintenance

- Run secret scan before each PR: `python scripts/validation/secret_scan.py`
- Keep `private/` and `C:\AarohanSecrets\` out of Git
- Rotate any credential ever pasted into chat or committed by mistake
- Review Google OAuth authorized apps quarterly

## Pre-production checklist

Before future VPS deployment:

1. New production-only secrets (do not copy local vault)
2. Enable scheduling only with approval workflow reviewed
3. TLS termination via reverse proxy
4. Automated encrypted backups + tested restore
5. `SCHEDULING_ENABLED` and external send flags explicitly set per policy
6. All release gates in `docs/09_RELEASE_GATES.md` green

## Related

- Local ops: `docs/runbooks/LOCAL_DEVELOPMENT.md`
- Secret strategy: `docs/11_LOCAL_FIRST_SECRET_STRATEGY.md`
- Security policy: `docs/07_SECURITY.md`
