# Local Development Runbook

> **Canonical execution guide:** [LOCAL-APPLICATION-EXECUTION.md](LOCAL-APPLICATION-EXECUTION.md)  
> Use that document for prerequisites, versions, start/stop, all scripts, testing layers, and troubleshooting.

This file is a short index for discoverability.

## Start here

```powershell
cd C:\Development\Workspace\aarohan-careeros
pwsh .\scripts\local\Bootstrap-Aarohan.ps1      # once per machine
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached
```

Open http://localhost:3000/login — credentials from SecretStore (`ADMIN_EMAIL` / `ADMIN_PASSWORD`).

## Validate

```powershell
pwsh .\scripts\local\Test-Aarohan.ps1
pwsh .\scripts\validation\Verify-Full-R2.ps1
```

## Related

- [LOCAL-APPLICATION-EXECUTION.md](LOCAL-APPLICATION-EXECUTION.md) — full runbook
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [GOOGLE_OAUTH.md](GOOGLE_OAUTH.md)
- [BACKUP_RESTORE.md](BACKUP_RESTORE.md)
