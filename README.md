# Aarohan CareerOS

Supervised career operations system — job ingestion, evidence-based scoring, application packets, interview prep, and consulting workflows. **Local-first** development mode with human approval for all external actions.

## What it does

- Ingest jobs from public ATS feeds, manual URLs, dedicated Gmail labels, and the Ad Hoc Opportunity Studio
- Score and deduplicate with transparent, deterministic rules + bounded AI assist
- Generate resumes and cover letters grounded in Career Vault evidence
- Manage approval queues — no automatic submission or outbound email
- Google Drive sync and Gmail read (dedicated account configured via `CAREER_GMAIL_ADDRESS`)
- Full dashboard, audit log, and AI spend controls

**Stack:** FastAPI + PostgreSQL + Next.js + n8n (optional), orchestrated via Docker Compose on Windows.

## Sign in

| Item | Value |
|------|-------|
| Dashboard | http://localhost:3000 |
| Settings | http://localhost:3000/settings |
| Login email | `ADMIN_EMAIL` from local secrets |
| Login password | `ADMIN_PASSWORD` from local secrets |

Configure credentials once:

```powershell
powershell -File scripts/local/Initialize-LocalSecrets.ps1
```

Reset admin password (interactive — never commit the value):

```powershell
powershell -File scripts/local/Reset-LocalAdmin.ps1 -Force
```

### Services

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API health | http://localhost:8000/health |
| API docs | http://localhost:8000/docs |
| n8n (optional profile) | http://localhost:5678 |

### Google integration

- **OAuth account:** dedicated career Gmail (`CAREER_GMAIL_ADDRESS` in secrets)
- **Scopes:** `openid`, `userinfo.email`, `userinfo.profile`, `drive.file`, `gmail.readonly`
- **Drive root:** app-created private folder stored in database metadata — reused across restarts

Use **Connect Google** in Settings on first setup. Reconnect only when refresh tokens are revoked or scopes change.

## Quick start

```powershell
# One-time setup
powershell -File scripts/local/Bootstrap-Aarohan.ps1
powershell -File scripts/local/Initialize-LocalSecrets.ps1

# Start core stack (postgres + api + web)
powershell -File scripts/local/Start-Aarohan.ps1 -Detached

# Optional n8n
powershell -File scripts/local/Start-Aarohan.ps1 -Detached -WithN8n

# Validate
powershell -File scripts/local/Test-Aarohan.ps1
```

### Restart / status

```powershell
docker compose ps
powershell -File scripts/local/Import-LocalSecrets.ps1
powershell -File scripts/local/Start-Aarohan.ps1 -Detached
powershell -File scripts/local/Test-Aarohan.ps1
```

**Stop:** `powershell -File scripts/local/Stop-Aarohan.ps1`

## Documentation

### Architecture

- [System architecture](docs/architecture/ARCHITECTURE.md)

### Runbooks

- [Local development](docs/runbooks/LOCAL_DEVELOPMENT.md)
- [Google OAuth](docs/runbooks/GOOGLE_OAUTH.md)
- [Troubleshooting](docs/runbooks/TROUBLESHOOTING.md)
- [Backup & restore](docs/runbooks/BACKUP_RESTORE.md)

### Testing & release

- [Test strategy](docs/testing/TEST_STRATEGY.md)
- [UAT runbook](docs/testing/UAT_RUNBOOK.md)
- [R1 local complete](docs/releases/R1_LOCAL_COMPLETE.md)

## Security

- Secrets in `C:\AarohanSecrets\aarohan.local.env` — not Git
- OAuth client JSON at `C:\AarohanSecrets\google-oauth-client.json`
- OAuth tokens encrypted at rest (`TOKEN_ENCRYPTION_KEY`)
- No LinkedIn/Indeed scraping; no automatic submission or messaging

## Not enabled in local-first mode

- Cloud deployment
- Production schedules (`SCHEDULING_ENABLED=false`)
- External email send (`ENABLE_EXTERNAL_EMAIL_SEND=false`)
- Automatic final application submission

## Validation artifacts

- `validation/CURSOR_TEST_EVIDENCE.md`
- `validation/CURSOR_END_TO_END_DEMO.md`
- `validation/SECOND_REVIEW_HANDOFF.md`
- `validation/COWORK_UAT_PROMPT.md`
