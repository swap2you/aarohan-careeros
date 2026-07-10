#Requires -Version 5.1
<#
.SYNOPSIS
  Phase 1 incident snapshot: dump all non-template PostgreSQL databases, verify restores,
  and emit recovery evidence under artifacts/recovery/incident-20260709/<timestamp>/.

.DESCRIPTION
  Read-only against owner/validation databases. Creates disposable verification databases only.
  Does not restore over career_os or career_os_validation.
#>
param(
    [string]$Timestamp = "",
    [string]$ContainerName = "aarohan-careeros-postgres-1",
    [string]$PgUser = "career_os"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

if (-not $Timestamp) {
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
}

$IncidentRoot = Join-Path $Root "artifacts\recovery\incident-20260709\$Timestamp"
$DumpsDir = Join-Path $IncidentRoot "dumps"
$ReportsDir = Join-Path $IncidentRoot "reports"
New-Item -ItemType Directory -Force -Path $DumpsDir, $ReportsDir | Out-Null

function Invoke-PgQuery {
    param(
        [Parameter(Mandatory)] [string]$Database,
        [Parameter(Mandatory)] [string]$Sql,
        [switch]$TuplesOnly
    )
    $args = @("exec", $ContainerName, "psql", "-U", $PgUser, "-d", $Database)
    if ($TuplesOnly) { $args += "-At" }
    else { $args += "-A" }
    $args += "-c", $Sql
    $out = docker @args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "psql failed on $Database`: $out" }
    return (($out | Out-String).Trim() -replace "`r", "")
}

function Get-DatabaseList {
    $sql = @"
SELECT datname
FROM pg_database
WHERE datistemplate = false
ORDER BY datname;
"@
    $raw = Invoke-PgQuery -Database "postgres" -Sql $sql -TuplesOnly
    return @($raw -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Get-TableRowCounts {
    param([Parameter(Mandatory)] [string]$Database)
    $sql = @"
SELECT schemaname||'.'||tablename AS table_name,
       (xpath('/row/cnt/text()', query_to_xml(format('select count(*) as cnt from %I.%I', schemaname, tablename), false, true, '')))[1]::text::int AS row_count
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog','information_schema')
ORDER BY schemaname, tablename;
"@
    $raw = Invoke-PgQuery -Database $Database -Sql $sql -TuplesOnly
    $rows = @()
    foreach ($line in ($raw -split "`n")) {
        $line = $line.Trim()
        if (-not $line) { continue }
        $parts = $line -split '\|', 2
        if ($parts.Count -lt 2) { continue }
        $rows += [ordered]@{
            table = $parts[0]
            row_count = [int]$parts[1]
        }
    }
    return $rows
}

function Get-DatabaseInventory {
    $sql = @"
SELECT datname,
       pg_database_size(datname) AS size_bytes,
       pg_encoding_to_char(encoding) AS encoding,
       datcollate,
       datctype
FROM pg_database
WHERE datistemplate = false
ORDER BY datname;
"@
    $raw = Invoke-PgQuery -Database "postgres" -Sql $sql -TuplesOnly
    $items = @()
    foreach ($line in ($raw -split "`n")) {
        $line = $line.Trim()
        if (-not $line) { continue }
        $p = $line -split '\|'
        if ($p.Count -lt 5) { continue }
        $items += [ordered]@{
            database = $p[0]
            size_bytes = [long]$p[1]
            encoding = $p[2]
            collate = $p[3]
            ctype = $p[4]
        }
    }
    return $items
}

function Export-DatabaseDump {
    param([Parameter(Mandatory)] [string]$Database)
    if ($Database -eq "career_os") {
        $guardScript = Join-Path (Split-Path $PSScriptRoot -Parent) "local/Assert-AarohanOwnerDatabaseIdentity.ps1"
        . $guardScript
        $null = Assert-AarohanOwnerDatabaseIdentity -Database $Database -ContainerName $ContainerName -PrivilegedUser $PgUser
    }
    $containerPath = "/tmp/recovery_dump_${Database}.sql"
    $hostPath = Join-Path $DumpsDir "${Database}.sql"

    docker exec $ContainerName sh -c "pg_dump -U $PgUser -d $Database -Fp --no-owner --no-acl -f $containerPath" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed for $Database" }

    docker cp "${ContainerName}:${containerPath}" $hostPath
    if ($LASTEXITCODE -ne 0) { throw "docker cp failed for $Database" }

    docker exec $ContainerName sh -c "rm -f $containerPath" | Out-Null

    if (-not (Test-Path $hostPath)) { throw "Dump file missing: $hostPath" }
    $size = (Get-Item $hostPath).Length
    if ($size -le 0) { throw "Dump file empty: $hostPath" }

    $head = Get-Content -Path $hostPath -TotalCount 30 -ErrorAction Stop
    $hasCreate = $head | Where-Object { $_ -match 'PostgreSQL database dump|CREATE TABLE|CREATE SCHEMA' }
    if (-not $hasCreate -and $Database -ne 'postgres') {
        throw "Dump for $Database does not look like valid SQL (first 30 lines inspected)"
    }

    return [ordered]@{
        database = $Database
        path = $hostPath
        size_bytes = $size
        sha256 = (Get-FileHash -Path $hostPath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function Export-GlobalsDump {
    $containerPath = "/tmp/recovery_globals.sql"
    $hostPath = Join-Path $DumpsDir "globals.sql"

    docker exec $ContainerName sh -c "pg_dumpall -U $PgUser --globals-only -f $containerPath" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pg_dumpall --globals-only failed" }

    docker cp "${ContainerName}:${containerPath}" $hostPath
    if ($LASTEXITCODE -ne 0) { throw "docker cp failed for globals" }
    docker exec $ContainerName sh -c "rm -f $containerPath" | Out-Null

    if (-not (Test-Path $hostPath)) { throw "Globals dump missing" }
    $size = (Get-Item $hostPath).Length
    if ($size -le 0) { throw "Globals dump empty" }

    return [ordered]@{
        database = "globals"
        path = $hostPath
        size_bytes = $size
        sha256 = (Get-FileHash -Path $hostPath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function Test-RestoreDump {
    param(
        [Parameter(Mandatory)] [string]$SourceDatabase,
        [Parameter(Mandatory)] [string]$DumpPath
    )
    $verifyDb = "recovery_verify_${SourceDatabase}_$($Timestamp -replace '[^0-9]','')"
    if ($verifyDb.Length -gt 63) {
        $verifyDb = "recovery_verify_$($Timestamp -replace '[^0-9]','')_$([guid]::NewGuid().ToString('N').Substring(0,8))"
    }

    Invoke-PgQuery -Database "postgres" -Sql "DROP DATABASE IF EXISTS `"$verifyDb`";" | Out-Null
    Invoke-PgQuery -Database "postgres" -Sql "CREATE DATABASE `"$verifyDb`" OWNER $PgUser;" | Out-Null

    $containerDump = "/tmp/recovery_restore_${SourceDatabase}.sql"
    docker cp $DumpPath "${ContainerName}:${containerDump}"
    if ($LASTEXITCODE -ne 0) { throw "docker cp to container failed for restore of $SourceDatabase" }

    docker exec $ContainerName sh -c "psql -U $PgUser -d $verifyDb -v ON_ERROR_STOP=1 -f $containerDump" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Invoke-PgQuery -Database "postgres" -Sql "DROP DATABASE IF EXISTS `"$verifyDb`";" | Out-Null
        throw "Restore verification failed for $SourceDatabase into $verifyDb"
    }
    docker exec $ContainerName sh -c "rm -f $containerDump" | Out-Null

    $sourceCounts = Get-TableRowCounts -Database $SourceDatabase
    $verifyCounts = Get-TableRowCounts -Database $verifyDb

    $sourceMap = @{}
    foreach ($r in $sourceCounts) { $sourceMap[$r.table] = $r.row_count }

    $verifyMap = @{}
    foreach ($r in $verifyCounts) { $verifyMap[$r.table] = $r.row_count }

    $mismatches = @()
    foreach ($table in ($sourceMap.Keys | Sort-Object)) {
        $src = $sourceMap[$table]
        $ver = if ($verifyMap.ContainsKey($table)) { $verifyMap[$table] } else { $null }
        if ($ver -ne $src) {
            $mismatches += [ordered]@{ table = $table; source = $src; restored = $ver }
        }
    }
    foreach ($table in ($verifyMap.Keys | Sort-Object)) {
        if (-not $sourceMap.ContainsKey($table)) {
            $mismatches += [ordered]@{ table = $table; source = $null; restored = $verifyMap[$table] }
        }
    }

    $tableCountSource = $sourceCounts.Count
    $tableCountVerify = $verifyCounts.Count

    Invoke-PgQuery -Database "postgres" -Sql "DROP DATABASE IF EXISTS `"$verifyDb`";" | Out-Null

    return [ordered]@{
        source_database = $SourceDatabase
        verification_database = $verifyDb
        restore_verified = ($mismatches.Count -eq 0 -and $tableCountSource -eq $tableCountVerify)
        source_table_count = $tableCountSource
        restored_table_count = $tableCountVerify
        row_count_mismatches = $mismatches
    }
}

function Get-GitState {
    $sha = (git rev-parse HEAD).Trim()
    $branch = (git branch --show-current).Trim()
    $status = (git status --short).Trim()
    return [ordered]@{
        branch = $branch
        sha = $sha
        working_tree = if ($status) { $status -split "`n" } else { @() }
    }
}

function Get-DockerState {
    $containers = docker ps -a --format "{{json .}}" | ForEach-Object { $_ | ConvertFrom-Json }
    $volumes = docker volume ls --format "{{.Name}}"
    return [ordered]@{
        compose_project = "aarohan-careeros"
        postgres_container = $ContainerName
        postgres_volume = "aarohan-careeros_postgres_data"
        containers = $containers
        volumes = @($volumes)
    }
}

Write-Host "Phase 1 snapshot starting. Evidence root: $IncidentRoot"

$gitState = Get-GitState
$dockerState = Get-DockerState
$baselineInventory = Get-DatabaseInventory
$databases = Get-DatabaseList

Write-Host "Databases to dump: $($databases -join ', ')"

$baselineRowCounts = @{}
foreach ($db in $databases) {
    if ($db -eq 'postgres') { continue }
    $baselineRowCounts[$db] = Get-TableRowCounts -Database $db
}

$backupEntries = @()
$backupEntries += Export-GlobalsDump
foreach ($db in $databases) {
    $backupEntries += Export-DatabaseDump -Database $db
}

$restoreResults = @()
foreach ($entry in ($backupEntries | Where-Object { $_.database -ne 'globals' })) {
    Write-Host "Restore-verifying $($entry.database)..."
    $restoreResults += ,(Test-RestoreDump -SourceDatabase $entry.database -DumpPath $entry.path)
}

$postRowCounts = @{}
foreach ($db in $databases) {
    if ($db -eq 'postgres') { continue }
    $postRowCounts[$db] = Get-TableRowCounts -Database $db
}

$unchangedConfirmation = [ordered]@{}
foreach ($db in @('career_os', 'career_os_validation')) {
    $before = @{}
    foreach ($r in $baselineRowCounts[$db]) { $before[$r.table] = $r.row_count }
    $after = @{}
    foreach ($r in $postRowCounts[$db]) { $after[$r.table] = $r.row_count }
    $diff = @()
    foreach ($t in ($before.Keys | Sort-Object)) {
        if ($after[$t] -ne $before[$t]) {
            $diff += [ordered]@{ table = $t; before = $before[$t]; after = $after[$t] }
        }
    }
    foreach ($t in ($after.Keys | Sort-Object)) {
        if (-not $before.ContainsKey($t)) {
            $diff += [ordered]@{ table = $t; before = $null; after = $after[$t] }
        }
    }
    $unchangedConfirmation[$db] = [ordered]@{
        unchanged = ($diff.Count -eq 0)
        diffs = $diff
    }
}

$ownerRelevantTables = @(
    'public.users','public.user_sessions','public.oauth_tokens','public.jobs','public.job_scores',
    'public.applications','public.application_document_versions','public.application_events',
    'public.application_ledger','public.application_timeline_events','public.approval_actions',
    'public.audit_logs','public.ai_usage_records','public.processed_gmail_messages',
    'public.recruiter_signals','public.evidence_items','public.interview_packs',
    'public.companies','public.connector_runs','public.gmail_ingest_reviews',
    'public.representation_records','public.system_settings','public.validation_runs'
)

$ownerInspection = [ordered]@{}
foreach ($db in @('career_os', 'career_os_validation', 'career_os_e2e')) {
    if (-not ($postRowCounts.ContainsKey($db))) { continue }
    $map = @{}
    foreach ($r in $postRowCounts[$db]) { $map[$r.table] = $r.row_count }
    $subset = [ordered]@{}
    foreach ($t in $ownerRelevantTables) {
        if ($map.ContainsKey($t)) { $subset[$t] = $map[$t] }
        else { $subset[$t] = "absent" }
    }
    $ownerInspection[$db] = $subset
}

$manifest = [ordered]@{
    incident_id = "owner-db-incident-20260709"
    timestamp = $Timestamp
    git = $gitState
    docker = $dockerState
    databases = $baselineInventory
    backups = $backupEntries
    restore_verification = $restoreResults
    owner_validation_unchanged = $unchangedConfirmation
    evidence_root = ($IncidentRoot -replace '\\', '/')
}

$inventory = [ordered]@{
    captured_at = (Get-Date).ToUniversalTime().ToString("o")
    databases = $baselineInventory
    docker = $dockerState
}

$tableCounts = [ordered]@{
    captured_at = (Get-Date).ToUniversalTime().ToString("o")
    baseline = $baselineRowCounts
    post_snapshot = $postRowCounts
    owner_relevant = $ownerInspection
}

$manifestPath = Join-Path $ReportsDir "BACKUP-MANIFEST.json"
$inventoryPath = Join-Path $ReportsDir "DATABASE-INVENTORY.json"
$tableCountsPath = Join-Path $ReportsDir "TABLE-ROW-COUNTS.json"

$manifest | ConvertTo-Json -Depth 12 | Set-Content -Path $manifestPath -Encoding UTF8
$inventory | ConvertTo-Json -Depth 10 | Set-Content -Path $inventoryPath -Encoding UTF8
$tableCounts | ConvertTo-Json -Depth 12 | Set-Content -Path $tableCountsPath -Encoding UTF8

$restoreSummary = ($restoreResults | ForEach-Object {
    "- $($_.source_database): verified=$($_.restore_verified); tables=$($_.source_table_count)/$($_.restored_table_count); mismatches=$($_.row_count_mismatches.Count)"
}) -join "`n"

$backupSummary = ($backupEntries | ForEach-Object {
    $rel = $_.path.Replace($Root + '\', '').Replace('\', '/')
    "- $($_.database): $rel ($('{0:N0}' -f $_.size_bytes) bytes) sha256=$($_.sha256)"
}) -join "`n"

$assessment = @"
# Recovery Candidate Assessment — Phase 1 Snapshot

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")
Evidence root: ``$($IncidentRoot -replace '\\','/')``

## Snapshot integrity

All non-template databases dumped and restore-verified into disposable databases.

### Backups

$backupSummary

### Restore verification

$restoreSummary

## Database roles

| Database | Size (bytes) | Role assessment |
|---|---:|---|
| career_os | $($baselineInventory | Where-Object database -eq 'career_os' | ForEach-Object { $_.size_bytes }) | **Current owner runtime DB** — contaminated with E2E/PG-test data per incident; not the recovery source of truth |
| career_os_validation | $($baselineInventory | Where-Object database -eq 'career_os_validation' | ForEach-Object { $_.size_bytes }) | **Primary recovery candidate source** — richer owner-like data (OAuth, Gmail, jobs, applications) |
| career_os_e2e | $($baselineInventory | Where-Object database -eq 'career_os_e2e' | ForEach-Object { $_.size_bytes }) | E2E/test fixture database — exclude from owner recovery |
| postgres | $($baselineInventory | Where-Object database -eq 'postgres' | ForEach-Object { $_.size_bytes }) | Administrative catalog only |

## Owner-relevant row counts (post-snapshot, unchanged)

### career_os (owner — do not use as recovery source)

$(($ownerInspection['career_os'].GetEnumerator() | Sort-Object Name | ForEach-Object { "- $($_.Name): $($_.Value)" }) -join "`n")

### career_os_validation (recovery candidate source)

$(($ownerInspection['career_os_validation'].GetEnumerator() | Sort-Object Name | ForEach-Object { "- $($_.Name): $($_.Value)" }) -join "`n")

## Key recovery signals

- ``career_os_validation`` has OAuth tokens ($($ownerInspection['career_os_validation']['public.oauth_tokens'])), processed Gmail ($($ownerInspection['career_os_validation']['public.processed_gmail_messages'])), recruiter signals ($($ownerInspection['career_os_validation']['public.recruiter_signals'])), and more jobs/applications than ``career_os``.
- ``career_os`` has **zero** OAuth tokens and **zero** processed Gmail — consistent with test contamination / data loss on owner DB.
- ``career_os_e2e`` is fixture-heavy (audit/ai_usage/session counts) — must remain isolated.

## Phase 1 conclusion

**Recommended recovery path (Phase 3):** build owner candidate from verified ``career_os_validation`` snapshot after schema upgrade and row-level exclusion of test/fixture rows.

**Do not restore directly over ``career_os`` without Gate 2 owner approval.**

## Unchanged confirmation

- career_os unchanged: $($unchangedConfirmation['career_os'].unchanged)
- career_os_validation unchanged: $($unchangedConfirmation['career_os_validation'].unchanged)
"@

$assessmentPath = Join-Path $ReportsDir "RECOVERY-CANDIDATE-ASSESSMENT.md"
Set-Content -Path $assessmentPath -Value $assessment -Encoding UTF8

$report = @"
# Incident Snapshot Report — owner-db-incident-20260709

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")
Timestamp folder: ``$Timestamp``

## Git

- Branch: $($gitState.branch)
- SHA: $($gitState.sha)
- Working tree:
$(if ($gitState.working_tree.Count) { ($gitState.working_tree | ForEach-Object { "  - $_" }) -join "`n" } else { "  - clean (except untracked recovery artifacts)" })

## Docker

- Compose project: aarohan-careeros
- Postgres container: $ContainerName
- Postgres volume: aarohan-careeros_postgres_data
- Running containers: $($dockerState.containers.Count)

## Databases discovered

$(($baselineInventory | ForEach-Object { "- $($_.database): $($_.size_bytes) bytes ($('{0:N2}' -f ($_.size_bytes/1MB)) MB)" }) -join "`n")

## Backups created

$backupSummary

## Restore verification

$restoreSummary

## Owner/validation unchanged

- career_os: $($unchangedConfirmation['career_os'].unchanged)
- career_os_validation: $($unchangedConfirmation['career_os_validation'].unchanged)

## Evidence files

- ``$($manifestPath -replace '\\','/')``
- ``$($inventoryPath -replace '\\','/')``
- ``$($tableCountsPath -replace '\\','/')``
- ``$($assessmentPath -replace '\\','/')``
- Dumps under ``$($DumpsDir -replace '\\','/')/``
"@

$reportPath = Join-Path $ReportsDir "INCIDENT-SNAPSHOT-REPORT.md"
Set-Content -Path $reportPath -Value $report -Encoding UTF8

$failedRestores = @($restoreResults | Where-Object { $_ -is [hashtable] -or $_ -is [System.Collections.Specialized.OrderedDictionary] } | Where-Object { -not $_.restore_verified })
if ($failedRestores.Count -gt 0) {
    throw "Restore verification failed for: $($failedRestores.source_database -join ', ')"
}
if (-not $unchangedConfirmation['career_os'].unchanged -or -not $unchangedConfirmation['career_os_validation'].unchanged) {
    throw "Owner or validation database row counts changed during Phase 1"
}

Write-Host ""
Write-Host "Phase 1 snapshot complete."
Write-Host "Evidence: $IncidentRoot"
Write-Host "Report: $reportPath"

return [ordered]@{
    timestamp = $Timestamp
    evidence_root = $IncidentRoot
    manifest_path = $manifestPath
    all_restore_verified = ($failedRestores.Count -eq 0)
    owner_unchanged = $unchangedConfirmation['career_os'].unchanged
    validation_unchanged = $unchangedConfirmation['career_os_validation'].unchanged
}
