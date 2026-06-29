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

## R1 local checkpoint (2026-06-28)

Proven on local Docker: OAuth connected, app-owned Drive root, idempotent subfolders, fixture packet + Drive upload, 29 pytest / scans pass.

### Sign in

| Item | Value |
|------|-------|
| Dashboard | http://localhost:3000 |
| Settings | http://localhost:3000/settings |
| Login email | `swapnilpatil.tech@gmail.com` |
| Local password | `TempLocal123!` (local dev only) |
| Reset admin | `powershell -File scripts/local/Reset-LocalAdmin.ps1 -Force` |

### Services

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API health | http://localhost:8000/health |
| API docs | http://localhost:8000/docs |
| n8n | http://localhost:5678 |

### Google integration

- **OAuth account:** `swapnilpatil.tech@gmail.com`
- **Scopes:** `openid`, `userinfo.email`, `userinfo.profile`, `drive.file`, `gmail.readonly`
- **Configured manual Drive root** (`1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr`): inaccessible with `drive.file` (expected)
- **Active app-created root:** `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr` (folder `aarohan-careeros`)

Use **Create Aarohan Drive Root** in Settings if Drive sync is unavailable after OAuth.

## Quick start

```powershell
# One-time setup
powershell -File scripts/local/Bootstrap-Aarohan.ps1
powershell -File scripts/local/Initialize-AarohanSecrets.ps1

# Start full stack
powershell -File scripts/local/Start-Aarohan.ps1 -Detached

# Validate
powershell -File scripts/local/Test-Aarohan.ps1
```

### Restart / status

```powershell
docker compose ps
docker compose up -d
docker compose down
powershell -File scripts/local/Start-Aarohan.ps1 -Detached
powershell -File scripts/local/Test-Aarohan.ps1
```

**Stop:** `powershell -File scripts/local/Stop-Aarohan.ps1`

## Known gaps (next session)

- Document quality needs improvement
- ATS templates need validation
- Real Gmail content still needs more test data
- GitHub Actions needs verification
- Playwright coverage needs expansion
- Backup/restore n8n schema noise
- UI polish pending

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

- Secrets in PowerShell SecretStore — not Git
- OAuth client JSON at `C:\AarohanSecrets\google-oauth-client.json`
- OAuth tokens encrypted at rest
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
