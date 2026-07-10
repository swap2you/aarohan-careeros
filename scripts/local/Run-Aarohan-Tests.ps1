#Requires -Version 5.1
<#
.SYNOPSIS
  Canonical Aarohan test runner — isolated infrastructure only; never targets owner career_os.

.DESCRIPTION
  1. Validation scans (including owner-stack pytest scan)
  2. Host SQLite unit tests (apps/api)
  3. Isolated postgres integration tests against test stack (127.0.0.1:5433)
  4. Optional Playwright against api-e2e/web-e2e

  Does NOT run pytest inside owner api container.
#>
param(
    [switch]$SkipPlaywright,
    [switch]$SkipPostgresIntegration
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
. (Join-Path $PSScriptRoot "Invoke-AarohanTestCompose.ps1")

function Run-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "`n>> $Name"
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

Write-Host "=== Run-Aarohan-Tests (isolated infrastructure) ==="

Run-Step "Secret scan" { python scripts/validation/secret_scan.py }
Run-Step "Prohibited source scan" { python scripts/validation/prohibited_source_scan.py }
Run-Step "Owner-stack pytest scan" { python scripts/validation/owner_stack_pytest_scan.py }

Push-Location apps/api
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\pip install -r requirements.txt -q
Run-Step "Backend unit tests (SQLite)" {
    $env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
    Remove-Item Env:AAROHAN_DB_IDENTITY_PURPOSE -ErrorAction SilentlyContinue
    .\.venv\Scripts\pytest -q
}
Pop-Location

if (-not $SkipPostgresIntegration) {
    Import-AarohanTestEnv -Root $Root

    $pgReady = docker exec aarohan-careeros-test-postgres-e2e-1 pg_isready -U career_os_e2e -d career_os_e2e 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Test postgres not running — starting isolated stack..."
        & pwsh -NoProfile -File (Join-Path $PSScriptRoot "Start-Aarohan-E2E.ps1")
    } else {
        & pwsh -NoProfile -File (Join-Path $PSScriptRoot "Invoke-ProvisionE2EDatabase.ps1") -RunMigrations
    }

    $bootstrapUrl = "postgresql+psycopg://career_os_e2e:$($env:E2E_POSTGRES_PASSWORD)@127.0.0.1:5433/career_os_e2e"
    $migrateUrl = "postgresql+psycopg://career_os_e2e_migrate:$($env:E2E_MIGRATE_PASSWORD)@127.0.0.1:5433/career_os_e2e"
    $pgUrl = "postgresql+psycopg://career_os_e2e_runtime:$($env:E2E_RUNTIME_PASSWORD)@127.0.0.1:5433/career_os_e2e"
    Push-Location apps/api
    Run-Step "Postgres integration tests (isolated career_os_e2e on :5433)" {
        $env:BOOTSTRAP_DATABASE_URL = $bootstrapUrl
        $env:MIGRATION_DATABASE_URL = $migrateUrl
        $env:DATABASE_URL = $pgUrl
        $env:AAROHAN_DB_IDENTITY_PURPOSE = "E2E"
        $env:AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_E2E_DB_IDENTITY_UUID
        $env:AAROHAN_RUNTIME_PROFILE = "test"
        .\.venv\Scripts\pytest tests/test_duplicate_risk_postgres.py tests/test_postgres_reset_guard.py tests/test_database_identity.py tests/test_database_identity_marker_postgres.py tests/test_database_roles_postgres.py tests/test_verified_backup_gate.py tests/test_migrations.py -q
    }
    Pop-Location
}

if (-not $SkipPlaywright) {
    Push-Location apps/web
    if (-not (Test-Path node_modules)) { npm install --silent }
    Run-Step "Playwright (isolated E2E stack)" {
        $env:PLAYWRIGHT_API_BASE = "http://127.0.0.1:8001"
        $env:PLAYWRIGHT_WEB_BASE = "http://127.0.0.1:3001"
        npx playwright test
    }
    Pop-Location
}

Write-Host "`nRun-Aarohan-Tests complete (owner career_os not used)."
