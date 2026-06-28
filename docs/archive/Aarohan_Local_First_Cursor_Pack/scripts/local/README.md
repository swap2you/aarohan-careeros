# Local Scripts

Cursor must implement and validate:

- `Initialize-AarohanSecrets.ps1`
- `Start-Aarohan.ps1`
- `Stop-Aarohan.ps1`
- `Test-Aarohan.ps1`

The scripts should use PowerShell SecretManagement and SecretStore.

Expected operator flow:

```powershell
pwsh .\scripts\local\Initialize-AarohanSecrets.ps1
pwsh .\scripts\local\Start-Aarohan.ps1
pwsh .\scripts\local\Test-Aarohan.ps1
pwsh .\scripts\local\Stop-Aarohan.ps1
```

No secret value should be printed or stored in the repository.
