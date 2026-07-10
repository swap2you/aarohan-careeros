#Requires -Version 5.1
<#
.SYNOPSIS
  Provision owner PostgreSQL migrate/runtime roles and immutable identity marker.
#>
param(
    [switch]$RunMigrations
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

$required = @(
    "POSTGRES_PASSWORD",
    "POSTGRES_MIGRATE_PASSWORD",
    "POSTGRES_RUNTIME_PASSWORD",
    "AAROHAN_OWNER_DB_IDENTITY_UUID"
)
foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Missing required value in .env.local: $name"
    }
}

$bootstrapUrl = "postgresql+psycopg://career_os:$($env:POSTGRES_PASSWORD)@127.0.0.1:5432/career_os"
$env:BOOTSTRAP_DATABASE_URL = $bootstrapUrl
$env:AAROHAN_DB_IDENTITY_PURPOSE = "OWNER"
$env:AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_OWNER_DB_IDENTITY_UUID

if ($RunMigrations) {
    $env:MIGRATION_DATABASE_URL = "postgresql+psycopg://career_os:$($env:POSTGRES_PASSWORD)@127.0.0.1:5432/career_os"
    $env:DATABASE_URL = $env:MIGRATION_DATABASE_URL
    Push-Location apps/api
    if (-not (Test-Path .venv)) { python -m venv .venv }
    .\.venv\Scripts\pip install -r requirements.txt -q
  .\.venv\Scripts\python -m alembic upgrade head
    Pop-Location
    if ($LASTEXITCODE -ne 0) { throw "Alembic upgrade failed before provisioning" }
}

Push-Location apps/api
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\pip install -r requirements.txt -q
$env:PYTHONPATH = "."
$output = .\.venv\Scripts\python scripts/provision_database_roles.py --stack owner 2>&1 | Out-String
Pop-Location
if ($LASTEXITCODE -ne 0) { throw "Owner role provisioning failed: $output" }
Write-Host $output.Trim()

Write-Host "Owner database roles and identity marker provisioned."
