# Aarohan CareerOS

Supervised career operations system — job ingestion, evidence-based scoring, application packets, interview prep, and consulting workflows. **Local-first** development mode with human approval for all external actions.

## What it does

- Ingest jobs from public ATS feeds, manual URLs, and dedicated Gmail labels
- Score and deduplicate with transparent, deterministic rules + bounded AI assist
- Generate resumes and cover letters grounded in Career Vault evidence
- Manage approval queues — no automatic submission or outbound email
- Google Drive sync and Gmail read (dedicated account: `swapnilpatil.tech@gmail.com`)
- Full dashboard, audit log, and AI spend controls

**Stack:** FastAPI + PostgreSQL + Next.js + n8n, orchestrated via Docker Compose on Windows.

## Quick start

```powershell
# One-time setup
pwsh .\scripts\local\Bootstrap-Aarohan.ps1
pwsh .\scripts\local\Initialize-AarohanSecrets.ps1

# Start full stack
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached

# Validate
pwsh .\scripts\local\Test-Aarohan.ps1
```

Open http://localhost:3000 and sign in with admin credentials from SecretStore.

**Stop:** `pwsh .\scripts\local\Stop-Aarohan.ps1`

## Local URLs

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| n8n | http://localhost:5678 |
| Health | http://localhost:8000/health |

## Documentation

### Architecture

- [System architecture](docs/architecture/ARCHITECTURE.md) — components, data flow, API surface

### Runbooks

- [Local development](docs/runbooks/LOCAL_DEVELOPMENT.md) — bootstrap, start/stop, Docker and direct-dev modes
- [Google OAuth](docs/runbooks/GOOGLE_OAUTH.md) — scopes, connect flow, dedicated account, remediation
- [Troubleshooting](docs/runbooks/TROUBLESHOOTING.md) — common errors and fixes
- [Backup & restore](docs/runbooks/BACKUP_RESTORE.md) — database backup scripts

### Testing & release

- [Test strategy](docs/testing/TEST_STRATEGY.md) — pytest, scans, Playwright, CI
- [UAT runbook](docs/testing/UAT_RUNBOOK.md) — manual acceptance testing

### Operations

- [Maintenance](docs/operations/MAINTENANCE.md) — schedules, secret rotation, updates

### Design references

- [Product scope](docs/01_PRODUCT_SCOPE.md)
- [Security](docs/07_SECURITY.md)
- [Release gates](docs/09_RELEASE_GATES.md)

## Security

- Secrets in PowerShell SecretStore — not Git
- OAuth client JSON at `C:\AarohanSecrets\google-oauth-client.json`
- OAuth tokens encrypted at rest
- No LinkedIn/Indeed scraping; no automatic submission or messaging
- Candidate source materials belong in `private/` only

## Not enabled in local-first mode

- Cloud deployment (by design)
- Production schedules (`SCHEDULING_ENABLED=false`)
- External email send (`ENABLE_EXTERNAL_EMAIL_SEND=false`)
- Automatic final application submission

## Validation artifacts

- `validation/COWORK_UAT_PROMPT.md`
- `validation/CURSOR_TEST_EVIDENCE.md`
- `validation/SECOND_REVIEW_HANDOFF.md`
