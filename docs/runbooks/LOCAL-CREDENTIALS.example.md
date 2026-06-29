# Local login credentials (template)

Copy to `LOCAL-CREDENTIALS.private.md` (gitignored) and fill in values.

## Owner / daily login

| Field | Value |
|-------|-------|
| URL | http://localhost:3000/login |
| Email | your-career@gmail.com |
| Password | (min 12 characters — SecretStore `ADMIN_PASSWORD`) |

## Playwright E2E only

| Field | Value |
|-------|-------|
| Email | e2e@test.local |
| Password | E2eTestPass123! |

```powershell
pwsh .\scripts\local\Ensure-E2ETestUser.ps1
```
