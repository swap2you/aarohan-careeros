# Fast Verification Plan

Use this checklist to verify the app quickly after clone, bootstrap, or RC validation.

**Full steps:** `docs/runbooks/LOCAL-APPLICATION-EXECUTION.md`

## Prerequisites verified

```powershell
git --version
python --version    # 3.12+
node --version      # 20+
docker compose version
```

## One-time setup

```powershell
pwsh .\scripts\local\Bootstrap-Aarohan.ps1
pwsh .\scripts\local\Initialize-AarohanSecrets.ps1
```

## Start and smoke

```powershell
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
start http://localhost:3000/login
```

## Automated gates

```powershell
pwsh .\scripts\local\Test-Aarohan.ps1
pwsh .\scripts\validation\Verify-Full-R2.ps1
docker compose exec -T api pytest tests/test_migrations.py tests/test_duplicate_risk_postgres.py -q
cd apps\web; npm run test:e2e
```

## Live checks (owner, optional)

```powershell
# Export OAUTH_FIXTURE_MODE=false from .env.local first
pwsh .\scripts\validation\Live-RC-Validation.ps1
```

Manual: Settings → Connect Google → ingest fixture jobs → generate packet → Gmail sync.

## Evidence locations

| Output | Path |
|--------|------|
| Full gate report | `generated/validation-reports/verify-full-r2-*.txt` |
| Live validation | `generated/validation-reports/live-rc-*.json` |
| Playwright | `artifacts/playwright/` |
| Backups | `artifacts/backups/` |

Do not make architecture changes until these checks pass.
