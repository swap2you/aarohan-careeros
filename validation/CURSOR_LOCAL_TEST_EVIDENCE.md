# Cursor Local Test Evidence

Date: 2026-06-24

## Commands executed

```powershell
# Backend tests
cd apps/api
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
$env:DATABASE_URL="sqlite+pysqlite:///:memory:"
$env:APP_SECRET="test-secret-key-32chars-minimum!"
$env:TOKEN_ENCRYPTION_KEY="test-token-encryption-key-32chars!"
$env:OAUTH_FIXTURE_MODE="true"
.\.venv\Scripts\pytest -q

# Validation scans
cd ../..
python scripts/validation/secret_scan.py
python scripts/validation/prohibited_source_scan.py

# Frontend build
cd apps/web
npm run build

# Local E2E smoke (no Docker)
cd ../api
$env:DATABASE_URL="sqlite+pysqlite:///./local_smoke.db"
$env:APP_SECRET="local-smoke-secret-32chars-min!"
$env:TOKEN_ENCRYPTION_KEY="local-smoke-token-key-32chars!!"
$env:OAUTH_FIXTURE_MODE="true"
.\.venv\Scripts\python scripts\local_smoke.py
```

## Results

| Check | Result |
|-------|--------|
| pytest | **13 passed** in 18.67s |
| secret_scan | **PASSED** |
| prohibited_source_scan | **PASSED** |
| npm run build | **SUCCESS** (12 routes) |
| local_smoke.py | **ALL STEPS PASSED** |

## Local smoke steps (all HTTP 200)

1. fixture_ingest  
2. public_ingest (Greenhouse gitlab board)  
3. packet_generate (DOCX/PDF)  
4. preview  
5. approve  
6. mark_submitted  
7. recruiter_fixture (Gmail fixture)  
8. interview_pack  
9. consulting_lead  
10. ai_budget  
11. audit_log  

## Docker status

Docker CLI **not available** in the Cursor agent execution environment (`docker: command not found`).  
User should verify locally:

```powershell
pwsh .\scripts\local\Initialize-AarohanSecrets.ps1
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached
pwsh .\scripts\local\Test-Aarohan.ps1
curl http://localhost:8000/health
curl http://localhost:3000
pwsh .\scripts\local\Stop-Aarohan.ps1
```

## Generated artifact paths (local smoke)

- SQLite DB: `apps/api/local_smoke.db`
- Resume output: under configured `generated_root` (Docker: `/app/generated`; local smoke may use fallback path)

## OAuth actions still requiring user

- Create Google Cloud OAuth client (Desktop/Web) for dedicated career Gmail
- Store `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` in SecretStore via `Initialize-AarohanSecrets.ps1`
- Complete browser consent for Gmail readonly + Drive file scopes
- Until then, use **OAuth fixture mode** (`OAUTH_FIXTURE_MODE=true`)

## Sample login flow (after Start-Aarohan)

1. Open http://localhost:3000  
2. First visit: create administrator (min 12-char password) OR use env bootstrap from SecretStore  
3. Jobs → Import Fixture → Generate Selected Packets → Approvals → Preview/Download  

## Unresolved defects

- WeasyPrint warning on Windows host (PDF quality best in Docker/Linux)  
- Playwright E2E not run in this session  
- Backup/restore not executed (requires running PostgreSQL container)  
- Restart persistence not executed (requires Docker)
