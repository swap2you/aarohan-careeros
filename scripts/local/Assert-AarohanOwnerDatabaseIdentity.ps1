#Requires -Version 5.1
<#
.SYNOPSIS
  Mandatory fail-closed owner database identity preflight for privileged helpers.
#>
param(
    [string]$Database = "career_os",
    [string]$ComposeProject = "aarohan-careeros",
    [string]$PostgresService = "postgres",
    [string]$ContainerName = "",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5432,
    [string]$PrivilegedUser = "career_os"
)

$ErrorActionPreference = "Stop"

$LocalScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $LocalScriptRoot) {
    throw "Assert-AarohanOwnerDatabaseIdentity could not resolve script path."
}

$Root = Split-Path (Split-Path $LocalScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $LocalScriptRoot "Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

$ownerUuid = $env:AAROHAN_OWNER_DB_IDENTITY_UUID
if ([string]::IsNullOrWhiteSpace($ownerUuid)) {
    throw "Missing AAROHAN_OWNER_DB_IDENTITY_UUID for owner identity preflight."
}
$env:AAROHAN_DB_IDENTITY_PURPOSE = "OWNER"
$env:AAROHAN_DB_IDENTITY_UUID = $ownerUuid

$forbiddenDatabases = @(
    "career_os_validation",
    "career_os_e2e",
    "career_os_test",
    "career_os_recovery",
    "career_os_owner_candidate"
)
if ($Database -in $forbiddenDatabases) {
    throw "Owner identity preflight rejected forbidden database '$Database'."
}
if ($Database -ne "career_os") {
    throw "Owner identity preflight requires database 'career_os', not '$Database'."
}
if ($ComposeProject -ne "aarohan-careeros") {
    throw "Owner identity preflight requires compose project 'aarohan-careeros', not '$ComposeProject'."
}
if ($ComposeProject -eq "aarohan-careeros-test") {
    throw "Owner identity preflight cannot use isolated test compose project."
}
if ($Port -eq 5433) {
    throw "Owner identity preflight cannot target isolated test postgres port 5433."
}

$purpose = "OWNER"
$identityUuid = $ownerUuid
if ($identityUuid -notmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$') {
    throw "AAROHAN_OWNER_DB_IDENTITY_UUID must be a valid UUID v4."
}

if (-not $ContainerName) {
    $ContainerName = "${ComposeProject}-${PostgresService}-1"
}
$containerState = docker inspect -f "{{.State.Running}}" $ContainerName 2>$null
if ($LASTEXITCODE -ne 0 -or $containerState -ne "true") {
    throw "Owner postgres container '$ContainerName' is not running."
}
if ($ContainerName -match "careeros-test") {
    throw "Owner identity preflight rejected test postgres container '$ContainerName'."
}

$bootstrapPassword = $env:POSTGRES_PASSWORD
if ([string]::IsNullOrWhiteSpace($bootstrapPassword)) {
    throw "POSTGRES_PASSWORD missing from .env.local for owner identity preflight."
}

$databaseUrl = "postgresql+psycopg://${PrivilegedUser}:$bootstrapPassword@${HostName}:${Port}/${Database}"

Push-Location (Join-Path $Root "apps/api")
if (-not (Test-Path .venv)) {
    python -m venv .venv
}
$env:PYTHONPATH = "."
$resultJson = .\.venv\Scripts\python scripts/validate_owner_database_identity.py `
    --database-url $databaseUrl `
    --database $Database `
    --compose-project $ComposeProject `
    --postgres-service $PostgresService `
    --postgres-container $ContainerName `
    --host $HostName `
    --port $Port `
    --privileged-user $PrivilegedUser 2>&1 | Out-String
Pop-Location

if ($LASTEXITCODE -ne 0) {
    $errorText = ($resultJson | ConvertFrom-Json -ErrorAction SilentlyContinue).error
    if (-not $errorText) { $errorText = $resultJson.Trim() }
    throw "Owner database identity preflight failed: $errorText"
}

$identity = $resultJson.Trim() | ConvertFrom-Json
if (-not $identity.verified) {
    throw "Owner database identity preflight returned verified=false."
}

return [ordered]@{
    Verified = $true
    Purpose = [string]$identity.purpose
    IdentityUuid = [string]$identity.identity_uuid
    Database = [string]$identity.database
    ComposeProject = [string]$identity.compose_project
    PostgresService = [string]$identity.postgres_service
    PostgresContainer = [string]$identity.postgres_container
    Host = [string]$identity.host
    Port = [int]$identity.port
    PrivilegedUser = [string]$identity.privileged_user
    IdentityFingerprint = [string]$identity.identity_fingerprint
    VerifiedAt = [string]$identity.verified_at
}
