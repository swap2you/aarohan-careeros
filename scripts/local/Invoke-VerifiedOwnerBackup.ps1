#Requires -Version 5.1
<#
.SYNOPSIS
  Create and restore-verify an owner career_os backup before destructive operations.
#>
param(
    [string]$Database = "career_os",
    [string]$ContainerName = "aarohan-careeros-postgres-1",
    [string]$BootstrapUser = "career_os",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

if (-not $OutputDir) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputDir = Join-Path $Root "artifacts\backups\verified_$stamp"
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$dumpHostPath = Join-Path $OutputDir "$Database.sql"
$manifestPath = Join-Path $OutputDir "BACKUP-MANIFEST.json"
$containerDump = "/tmp/verified_backup_${Database}.sql"
$verifyDb = "backup_verify_${Database}_$((Get-Date -Format 'yyyyMMddHHmmss'))"

function Invoke-PgAsBootstrap {
    param([Parameter(Mandatory)] [string]$Sql)
    docker exec $ContainerName psql -U $BootstrapUser -d postgres -v ON_ERROR_STOP=1 -c $Sql
    if ($LASTEXITCODE -ne 0) { throw "psql failed: $Sql" }
}

function Get-CriticalCounts {
    param([Parameter(Mandatory)] [string]$DbName)
    $raw = docker exec $ContainerName psql -U $BootstrapUser -d $DbName -Atc @"
SELECT 'jobs', count(*)::text FROM jobs
UNION ALL SELECT 'applications', count(*)::text FROM applications
UNION ALL SELECT 'users', count(*)::text FROM users
UNION ALL SELECT 'oauth_tokens', count(*)::text FROM oauth_tokens
UNION ALL SELECT 'processed_gmail_messages', count(*)::text FROM processed_gmail_messages;
"@
    $map = @{}
    foreach ($line in ($raw -split "`n")) {
        $line = $line.Trim()
        if (-not $line) { continue }
        $parts = $line -split '\|', 2
        if ($parts.Count -eq 2) { $map[$parts[0]] = [int]$parts[1] }
    }
    return $map
}

$sourceCounts = Get-CriticalCounts -DbName $Database
$sourceTables = docker exec $ContainerName psql -U $BootstrapUser -d $Database -Atc `
    "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema');"
if ($LASTEXITCODE -ne 0) { throw "Failed to read source table count" }
$sourceTables = [int]($sourceTables.Trim())

docker exec $ContainerName sh -c "pg_dump -U $BootstrapUser -d $Database -Fp --no-owner --no-acl -f $containerDump"
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }

docker cp "${ContainerName}:${containerDump}" $dumpHostPath
if ($LASTEXITCODE -ne 0) { throw "docker cp failed for backup dump" }
docker exec $ContainerName sh -c "rm -f $containerDump" | Out-Null

if (-not (Test-Path $dumpHostPath)) { throw "Backup file missing after pg_dump" }
$size = (Get-Item $dumpHostPath).Length
if ($size -le 0) { throw "Backup file is empty" }

$head = Get-Content -Path $dumpHostPath -TotalCount 20
if (-not ($head | Where-Object { $_ -match 'PostgreSQL database dump' })) {
    throw "Backup file does not contain PostgreSQL dump header"
}

$sha256 = (Get-FileHash -Path $dumpHostPath -Algorithm SHA256).Hash.ToLowerInvariant()

Invoke-PgAsBootstrap "DROP DATABASE IF EXISTS `"$verifyDb`";"
Invoke-PgAsBootstrap "CREATE DATABASE `"$verifyDb`" OWNER $BootstrapUser;"

docker cp $dumpHostPath "${ContainerName}:/tmp/restore_verify.sql"
if ($LASTEXITCODE -ne 0) { throw "docker cp to container failed for restore verification" }
docker exec $ContainerName sh -c "psql -U $BootstrapUser -d $verifyDb -v ON_ERROR_STOP=1 -f /tmp/restore_verify.sql" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Invoke-PgAsBootstrap "DROP DATABASE IF EXISTS `"$verifyDb`";"
    throw "Restore verification failed for $Database"
}
docker exec $ContainerName sh -c "rm -f /tmp/restore_verify.sql" | Out-Null

$restoredTables = docker exec $ContainerName psql -U $BootstrapUser -d $verifyDb -Atc `
    "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema');"
$restoredTables = [int]($restoredTables.Trim())
if ($restoredTables -ne $sourceTables) {
    Invoke-PgAsBootstrap "DROP DATABASE IF EXISTS `"$verifyDb`";"
    throw "Restored table count mismatch: source=$sourceTables restored=$restoredTables"
}

$restoredCounts = Get-CriticalCounts -DbName $verifyDb
foreach ($key in $sourceCounts.Keys) {
    if ($restoredCounts[$key] -ne $sourceCounts[$key]) {
        Invoke-PgAsBootstrap "DROP DATABASE IF EXISTS `"$verifyDb`";"
        throw "Row-count mismatch for $key`: source=$($sourceCounts[$key]) restored=$($restoredCounts[$key])"
    }
}

Invoke-PgAsBootstrap "DROP DATABASE IF EXISTS `"$verifyDb`";"

$manifest = [ordered]@{
    verified = $true
    database = $Database
    dump_path = ($dumpHostPath -replace '\\', '/')
    size_bytes = $size
    sha256 = $sha256
    source_table_count = $sourceTables
    restored_table_count = $restoredTables
    critical_row_counts = $sourceCounts
    verified_at = (Get-Date).ToUniversalTime().ToString('o')
    verification_database = $verifyDb
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding UTF8

return [ordered]@{
    Verified = $true
    ManifestPath = $manifestPath
    DumpPath = $dumpHostPath
    Sha256 = $sha256
    SizeBytes = $size
    CriticalRowCounts = $sourceCounts
}
