#Requires -Version 5.1
<#
.SYNOPSIS
  Create or refresh the Playwright e2e admin without removing the owner admin.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

$apiStatus = docker compose ps api --format "{{.Status}}" 2>$null
if (-not $apiStatus -or $apiStatus -notmatch "Up") {
    throw "API container is not running. Start stack first: pwsh scripts/local/Start-Aarohan.ps1 -Detached"
}

$e2ePassword = $env:E2E_TEST_PASSWORD
if (-not $e2ePassword) {
    try {
        Import-Module Microsoft.PowerShell.SecretManagement -ErrorAction Stop
        $e2ePassword = Get-Secret -Name E2E_TEST_PASSWORD -AsPlainText -ErrorAction Stop
    } catch { }
}
if (-not $e2ePassword) {
    throw "Set E2E_TEST_PASSWORD env or SecretStore secret (see LOCAL-CREDENTIALS.private.md)"
}

docker compose exec -T -e "E2E_TEST_PASSWORD=$e2ePassword" api python scripts/ensure_e2e_user.py
if ($LASTEXITCODE -ne 0) { throw "ensure_e2e_user failed" }
Write-Host "E2E user: e2e@test.local (password in docs/runbooks/LOCAL-CREDENTIALS.private.md)"
