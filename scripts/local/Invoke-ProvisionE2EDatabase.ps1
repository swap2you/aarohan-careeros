#Requires -Version 5.1
<#
.SYNOPSIS
  Provision isolated E2E PostgreSQL migrate/runtime roles and identity marker.
#>
param(
    [switch]$RunMigrations
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanTestCompose.ps1")
Import-AarohanTestEnv -Root $Root

$required = @(
    "E2E_POSTGRES_PASSWORD",
    "E2E_MIGRATE_PASSWORD",
    "E2E_RUNTIME_PASSWORD",
    "AAROHAN_E2E_DB_IDENTITY_UUID"
)
foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Missing required value in .env.local: $name"
    }
}

$bootstrapUrl = "postgresql+psycopg://career_os_e2e:$($env:E2E_POSTGRES_PASSWORD)@127.0.0.1:5433/career_os_e2e"
$env:BOOTSTRAP_DATABASE_URL = $bootstrapUrl
$env:AAROHAN_DB_IDENTITY_PURPOSE = "E2E"
$env:AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_E2E_DB_IDENTITY_UUID

if ($RunMigrations) {
    $env:MIGRATION_DATABASE_URL = $bootstrapUrl
    $env:DATABASE_URL = $bootstrapUrl
    Push-Location apps/api
    if (-not (Test-Path .venv)) { python -m venv .venv }
    .\.venv\Scripts\pip install -r requirements.txt -q
    $alembicVersion = docker exec aarohan-careeros-test-postgres-e2e-1 psql -U career_os_e2e -d career_os_e2e -Atc "SELECT version_num FROM alembic_version LIMIT 1" 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($alembicVersion)) {
        $hasUsers = docker exec aarohan-careeros-test-postgres-e2e-1 psql -U career_os_e2e -d career_os_e2e -Atc "SELECT to_regclass('public.users')" 2>$null
        if ($hasUsers -and $hasUsers.Trim() -eq "users") {
            Write-Host "E2E schema present without alembic_version — stamping 0012_fresh_jobs_discovery"
            .\.venv\Scripts\python -m alembic stamp 0012_fresh_jobs_discovery
            if ($LASTEXITCODE -ne 0) { throw "Alembic stamp failed for E2E database" }
        }
    }
    .\.venv\Scripts\python -m alembic upgrade head
    Pop-Location
    if ($LASTEXITCODE -ne 0) { throw "E2E Alembic upgrade failed before provisioning" }
}

Push-Location apps/api
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\pip install -r requirements.txt -q
$env:PYTHONPATH = "."
$output = .\.venv\Scripts\python scripts/provision_database_roles.py --stack e2e 2>&1 | Out-String
Pop-Location
if ($LASTEXITCODE -ne 0) { throw "E2E role provisioning failed: $output" }
Write-Host $output.Trim()
Write-Host "E2E database roles and identity marker provisioned."
