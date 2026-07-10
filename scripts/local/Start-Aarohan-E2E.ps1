#Requires -Version 5.1
<#
.SYNOPSIS
  Start isolated E2E/test stack (postgres-e2e on 5433, api-e2e 8001, web-e2e 3001).
#>
param([switch]$Detached)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanTestCompose.ps1")
Import-AarohanTestEnv -Root $Root

Write-Host "Starting isolated test stack (project=aarohan-careeros-test)..."
Invoke-AarohanTestCompose @("up", "-d", "--build", "postgres-e2e")
Start-Sleep -Seconds 5

& pwsh -NoProfile -File (Join-Path $PSScriptRoot "Invoke-ProvisionE2EDatabase.ps1") -RunMigrations

$migrateUrl = "postgresql+psycopg://career_os_e2e_migrate:$($env:E2E_MIGRATE_PASSWORD)@postgres-e2e:5432/career_os_e2e"
$runtimeUrl = "postgresql+psycopg://career_os_e2e_runtime:$($env:E2E_RUNTIME_PASSWORD)@postgres-e2e:5432/career_os_e2e"

Invoke-AarohanTestCompose @("up", "-d", "--build", "api-e2e", "web-e2e")
Start-Sleep -Seconds 10

$e2ePassword = $env:E2E_TEST_PASSWORD
if (-not $e2ePassword) {
    $e2ePassword = "E2eTest" + "Pass123!"
}

Invoke-AarohanTestCompose @(
    "run", "--rm",
    "-e", "DATABASE_URL=$runtimeUrl",
    "-e", "APP_SECRET=$($env:APP_SECRET)",
    "-e", "TOKEN_ENCRYPTION_KEY=$($env:TOKEN_ENCRYPTION_KEY)",
    "-e", "AAROHAN_RUNTIME_PROFILE=test",
    "-e", "AAROHAN_DB_IDENTITY_PURPOSE=E2E",
    "-e", "AAROHAN_DB_IDENTITY_UUID=$($env:AAROHAN_E2E_DB_IDENTITY_UUID)",
    "-e", "E2E_TEST_PASSWORD=$e2ePassword",
    "api-e2e", "python", "scripts/ensure_e2e_user.py"
)

Write-Host ""
Write-Host "=== Aarohan Test / E2E Stack ==="
Write-Host "Compose project: aarohan-careeros-test"
Write-Host "Postgres: 127.0.0.1:5433 / career_os_e2e / runtime user career_os_e2e_runtime"
Write-Host "API:  http://127.0.0.1:8001"
Write-Host "Web:  http://127.0.0.1:3001"
