#Requires -Version 5.1
<#
.SYNOPSIS
  Start isolated owner-candidate API (8002) and web (3002) against career_os_owner_candidate only.
#>
param(
    [switch]$SkipProvision
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
. (Join-Path $PSScriptRoot "Invoke-AarohanCandidateCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

$ContainerName = "aarohan-careeros-postgres-1"
$CandidateDatabase = "career_os_owner_candidate"
$PgUser = "career_os"
$HostName = "127.0.0.1"
$Port = 5432

function Invoke-PgQuery {
    param([string]$Database, [string]$Sql)
    if ($Database -in @("career_os", "career_os_validation")) {
        throw "Refusing query on forbidden database '$Database'"
    }
    docker exec $ContainerName psql -U $PgUser -d $Database -Atc $Sql
    if ($LASTEXITCODE -ne 0) { throw "psql failed on $Database" }
}

if (-not $SkipProvision) {
    $dbExists = Invoke-PgQuery -Database "postgres" -Sql "SELECT 1 FROM pg_database WHERE datname='$CandidateDatabase'"
    if (-not ($dbExists -match "1")) {
        throw "Database $CandidateDatabase does not exist. Run Phase 3 recovery first."
    }

    $marker = Invoke-PgQuery -Database $CandidateDatabase -Sql "SELECT identity_uuid FROM aarohan_meta.database_identity LIMIT 1"
    if ([string]::IsNullOrWhiteSpace($marker)) {
        throw "Missing OWNER_CANDIDATE identity marker in $CandidateDatabase"
    }
    $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID = $marker.Trim()

    if ([string]::IsNullOrWhiteSpace($env:CANDIDATE_MIGRATE_PASSWORD) -or [string]::IsNullOrWhiteSpace($env:CANDIDATE_RUNTIME_PASSWORD)) {
        throw "CANDIDATE_MIGRATE_PASSWORD and CANDIDATE_RUNTIME_PASSWORD required in .env.local"
    }

    Push-Location apps/api
    if (-not (Test-Path .venv)) { python -m venv .venv }
    $env:BOOTSTRAP_DATABASE_URL = "postgresql+psycopg://${PgUser}:$($env:POSTGRES_PASSWORD)@${HostName}:${Port}/${CandidateDatabase}"
    $env:PYTHONPATH = "."
    .\.venv\Scripts\python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Candidate alembic upgrade failed" }
    $env:AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    $env:AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID
    .\.venv\Scripts\python scripts/provision_database_roles.py --stack owner_candidate
    if ($LASTEXITCODE -ne 0) { throw "Candidate role provisioning failed" }
    Pop-Location
}

Invoke-AarohanCandidateCompose @("up", "-d", "--build")
Write-Host "Candidate runtime: API http://127.0.0.1:8002  Web http://127.0.0.1:3002"
Write-Host "Database: $CandidateDatabase (OWNER_CANDIDATE UUID $($env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID))"
