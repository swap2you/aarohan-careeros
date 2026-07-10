#Requires -Version 5.1
<#
.SYNOPSIS
  Mandatory fail-closed recovery / owner-candidate database identity preflight.
#>
param(
    [ValidateSet("RECOVERY", "OWNER_CANDIDATE")]
    [string]$Purpose = "RECOVERY",
    [string]$Database = "",
    [string]$ContainerName = "aarohan-careeros-postgres-1",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5432,
    [string]$PrivilegedUser = "career_os"
)

$ErrorActionPreference = "Stop"

$LocalScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path (Split-Path $LocalScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path (Split-Path $LocalScriptRoot -Parent) "local/Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

if (-not $Database) {
    $Database = if ($Purpose -eq "OWNER_CANDIDATE") { "career_os_owner_candidate" } else { "career_os_recovery" }
}
if ($Purpose -eq "RECOVERY") {
    if (-not $env:AAROHAN_RECOVERY_DB_IDENTITY_UUID) { throw "Missing AAROHAN_RECOVERY_DB_IDENTITY_UUID." }
    $env:AAROHAN_DB_IDENTITY_PURPOSE = "RECOVERY"
    $env:AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_RECOVERY_DB_IDENTITY_UUID
} else {
    if (-not $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID) { throw "Missing AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID." }
    $env:AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    $env:AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID
}

$forbidden = @("career_os", "career_os_validation", "career_os_e2e")
if ($Database -in $forbidden) {
    throw "Recovery preflight rejected forbidden database '$Database'."
}

$bootstrapPassword = $env:POSTGRES_PASSWORD
if ([string]::IsNullOrWhiteSpace($bootstrapPassword)) {
    throw "POSTGRES_PASSWORD missing for recovery preflight."
}

$databaseUrl = "postgresql+psycopg://${PrivilegedUser}:$bootstrapPassword@${HostName}:${Port}/${Database}"
$env:RECOVERY_DATABASE_URL = $databaseUrl

Push-Location (Join-Path $Root "apps/api")
if (-not (Test-Path .venv)) { python -m venv .venv }
$env:PYTHONPATH = "."
$resultJson = .\.venv\Scripts\python -c @"
import json, os, sys
sys.path.insert(0, '.')
from app.services.recovery_database_identity_preflight import validate_recovery_database_identity
result = validate_recovery_database_identity(database_url=os.environ['RECOVERY_DATABASE_URL'])
print(json.dumps(result.to_dict()))
"@ 2>&1 | Out-String
Pop-Location

if ($LASTEXITCODE -ne 0) {
    throw "Recovery database identity preflight failed: $resultJson"
}
$identity = $resultJson.Trim() | ConvertFrom-Json
if (-not $identity.verified) {
    throw "Recovery database identity preflight returned verified=false."
}
return [ordered]@{
    Verified = $true
    Purpose = [string]$identity.purpose
    IdentityUuid = [string]$identity.identity_uuid
    Database = [string]$identity.database
    IdentityFingerprint = [string]$identity.identity_fingerprint
    VerifiedAt = [string]$identity.verified_at
}
