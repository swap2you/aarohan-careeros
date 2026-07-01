#Requires -Version 5.1
<#
.SYNOPSIS
  Create or refresh the Playwright e2e admin on the isolated E2E stack only.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

Write-Host "Ensure-E2ETestUser.ps1 now targets the isolated E2E stack only."
Write-Host "Starting E2E services on ports 8001/3001 (career_os_e2e)..."

& (Join-Path $PSScriptRoot "Start-Aarohan-E2E.ps1") -Detached
if ($LASTEXITCODE -ne 0) { throw "Start-Aarohan-E2E.ps1 failed" }

Write-Host "E2E user: e2e@test.local (password from E2E_TEST_PASSWORD / SecretStore)"
Write-Host "Owner stack at http://localhost:3000 must NOT use the E2E account."
