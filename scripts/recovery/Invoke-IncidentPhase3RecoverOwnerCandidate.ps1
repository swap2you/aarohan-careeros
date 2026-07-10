#Requires -Version 5.1
<#
.SYNOPSIS
  Phase 3 owner candidate recovery orchestrator: staging, classification, candidate build,
  validation, and evidence emission. Does not cut over canonical owner database.

.DESCRIPTION
  Builds career_os_recovery from verified Phase 1 validation snapshot, upgrades schema in
  staging only, classifies rows, constructs career_os_owner_candidate, validates, backs up,
  and writes cutover/rollback plans. NEVER modifies career_os or career_os_validation.
#>
param(
    [string]$Timestamp = "",
    [string]$ContainerName = "aarohan-careeros-postgres-1",
    [string]$PgUser = "career_os"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $Root "scripts/local/Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

if (-not $Timestamp) {
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
}

$IncidentId = "owner-db-incident-20260709"
$Phase1EvidenceRoot = Join-Path $Root "artifacts\recovery\incident-20260709\20260709_172617"
$Phase1DumpPath = Join-Path $Phase1EvidenceRoot "dumps\career_os_validation.sql"
$ExpectedValidationDumpSha256 = "d44d2c57357f52ba296283601a6a2ab45b1ccd9ad68f95d8833b95fe3d7eddac"

$EvidenceRoot = Join-Path $Root "artifacts\recovery\incident-20260709\phase3-$Timestamp"
$ReportsDir = Join-Path $EvidenceRoot "reports"
$DumpsDir = Join-Path $EvidenceRoot "dumps"
New-Item -ItemType Directory -Force -Path $ReportsDir, $DumpsDir | Out-Null

$ForbiddenDatabases = @("career_os", "career_os_validation")
$RecoveryDatabase = "career_os_recovery"
$CandidateDatabase = "career_os_owner_candidate"
$HostName = "127.0.0.1"
$Port = 5432
$ApiDir = Join-Path $Root "apps\api"

$KeyTables = @("jobs", "applications", "oauth_tokens", "users", "processed_gmail_messages")
$ExecutionLog = [System.Collections.Generic.List[object]]::new()

function Add-StepLog {
    param(
        [Parameter(Mandatory)] [int]$Step,
        [Parameter(Mandatory)] [string]$Name,
        [string]$Status = "ok",
        [string]$Detail = ""
    )
    $ExecutionLog.Add([ordered]@{
        step = $Step
        name = $Name
        status = $Status
        detail = $Detail
        at = (Get-Date).ToUniversalTime().ToString("o")
    }) | Out-Null
}

function Assert-NotForbiddenDatabase {
    param([Parameter(Mandatory)] [string]$Database)
    if ($Database -in $ForbiddenDatabases) {
        throw "Refusing operation on forbidden database '$Database'. career_os and career_os_validation must never be modified."
    }
}

function New-SecurePassword {
    param([int]$Length = 32)
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $result = New-Object char[] $Length
    for ($i = 0; $i -lt $Length; $i++) {
        $result[$i] = $chars[$bytes[$i] % $chars.Length]
    }
    return -join $result
}

function Invoke-PgQuery {
    param(
        [Parameter(Mandatory)] [string]$Database,
        [Parameter(Mandatory)] [string]$Sql,
        [switch]$TuplesOnly
    )
    Assert-NotForbiddenDatabase -Database $Database
    $args = @("exec", $ContainerName, "psql", "-U", $PgUser, "-d", $Database)
    if ($TuplesOnly) { $args += "-At" }
    else { $args += "-A" }
    $args += "-c", $Sql
    $out = docker @args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "psql failed on $Database`: $out" }
    return (($out | Out-String).Trim() -replace "`r", "")
}

function Get-TableRowCounts {
    param([Parameter(Mandatory)] [string]$Database)
    Assert-NotForbiddenDatabase -Database $Database
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

function Get-OwnerValidationKeyRowCounts {
    $result = [ordered]@{}
    foreach ($db in $ForbiddenDatabases) {
        $raw = docker exec $ContainerName psql -U $PgUser -d $db -Atc @"
SELECT 'jobs', count(*)::text FROM jobs
UNION ALL SELECT 'applications', count(*)::text FROM applications
UNION ALL SELECT 'oauth_tokens', count(*)::text FROM oauth_tokens
UNION ALL SELECT 'users', count(*)::text FROM users
UNION ALL SELECT 'processed_gmail_messages', count(*)::text FROM processed_gmail_messages;
"@
        if ($LASTEXITCODE -ne 0) { throw "Failed to read key row counts from $db" }
        $map = @{}
        foreach ($line in ($raw -split "`n")) {
            $line = $line.Trim()
            if (-not $line) { continue }
            $parts = $line -split '\|', 2
            if ($parts.Count -eq 2) { $map[$parts[0]] = [int]$parts[1] }
        }
        $result[$db] = $map
    }
    return $result
}

function Compare-KeyRowCounts {
    param(
        [Parameter(Mandatory)] $Before,
        [Parameter(Mandatory)] $After
    )
    $diffs = @()
    foreach ($db in $ForbiddenDatabases) {
        foreach ($table in $KeyTables) {
            $b = $Before[$db][$table]
            $a = $After[$db][$table]
            if ($a -ne $b) {
                $diffs += [ordered]@{
                    database = $db
                    table = $table
                    before = $b
                    after = $a
                }
            }
        }
    }
    return $diffs
}

function Get-AlembicVersion {
    param([Parameter(Mandatory)] [string]$Database)
    Assert-NotForbiddenDatabase -Database $Database
    try {
        $version = Invoke-PgQuery -Database $Database -Sql "SELECT version_num FROM alembic_version LIMIT 1;" -TuplesOnly
        if ([string]::IsNullOrWhiteSpace($version)) { return "absent" }
        return $version.Trim()
    } catch {
        return "absent"
    }
}

function Restore-SqlDump {
    param(
        [Parameter(Mandatory)] [string]$TargetDatabase,
        [Parameter(Mandatory)] [string]$DumpPath
    )
    Assert-NotForbiddenDatabase -Database $TargetDatabase
    $containerDump = "/tmp/phase3_restore_${TargetDatabase}.sql"
    docker cp $DumpPath "${ContainerName}:${containerDump}"
    if ($LASTEXITCODE -ne 0) { throw "docker cp failed for restore into $TargetDatabase" }
    docker exec $ContainerName sh -c "psql -U $PgUser -d $TargetDatabase -v ON_ERROR_STOP=1 -f $containerDump" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Restore failed for $TargetDatabase from $DumpPath" }
    docker exec $ContainerName sh -c "rm -f $containerDump" | Out-Null
}

function Invoke-AlembicUpgrade {
    param(
        [Parameter(Mandatory)] [string]$Database,
        [Parameter(Mandatory)] [string]$Purpose,
        [Parameter(Mandatory)] [string]$IdentityUuid
    )
    Assert-NotForbiddenDatabase -Database $Database
    if ([string]::IsNullOrWhiteSpace($env:POSTGRES_PASSWORD)) {
        throw "POSTGRES_PASSWORD missing for alembic upgrade."
    }
    $bootstrapUrl = "postgresql+psycopg://${PgUser}:$($env:POSTGRES_PASSWORD)@${HostName}:${Port}/${Database}"
    $env:MIGRATION_DATABASE_URL = $bootstrapUrl
    $env:DATABASE_URL = $bootstrapUrl
    $env:AAROHAN_DB_IDENTITY_PURPOSE = $Purpose
    $env:AAROHAN_DB_IDENTITY_UUID = $IdentityUuid
    Push-Location $ApiDir
    if (-not (Test-Path .venv)) { python -m venv .venv }
    .\.venv\Scripts\pip install -r requirements.txt -q
    .\.venv\Scripts\python -m alembic upgrade head 2>&1 | Out-String | Out-Null
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { throw "Alembic upgrade failed for $Database (purpose=$Purpose)" }
}

function Invoke-ProvisionStack {
    param(
        [ValidateSet("recovery", "owner_candidate")]
        [string]$Stack,
        [Parameter(Mandatory)] [string]$Database,
        [Parameter(Mandatory)] [string]$Purpose,
        [Parameter(Mandatory)] [string]$IdentityUuid,
        [Parameter(Mandatory)] [string]$MigratePassword,
        [Parameter(Mandatory)] [string]$RuntimePassword
    )
    Assert-NotForbiddenDatabase -Database $Database
    $bootstrapUrl = "postgresql+psycopg://${PgUser}:$($env:POSTGRES_PASSWORD)@${HostName}:${Port}/${Database}"
    $env:BOOTSTRAP_DATABASE_URL = $bootstrapUrl
    $env:AAROHAN_DB_IDENTITY_PURPOSE = $Purpose
    $env:AAROHAN_DB_IDENTITY_UUID = $IdentityUuid
    if ($Stack -eq "recovery") {
        $env:RECOVERY_MIGRATE_PASSWORD = $MigratePassword
        $env:RECOVERY_RUNTIME_PASSWORD = $RuntimePassword
    } else {
        $env:CANDIDATE_MIGRATE_PASSWORD = $MigratePassword
        $env:CANDIDATE_RUNTIME_PASSWORD = $RuntimePassword
    }
    Push-Location $ApiDir
    if (-not (Test-Path .venv)) { python -m venv .venv }
    $env:PYTHONPATH = "."
    $output = .\.venv\Scripts\python scripts/provision_database_roles.py --stack $Stack 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { throw "Provisioning failed for stack=$Stack`: $output" }
    return $output.Trim()
}

function Parse-JsonFromOutput {
    param([string]$Text)
    $line = ($Text -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\{' } | Select-Object -Last 1)
    if (-not $line) { throw "No JSON object found in script output: $Text" }
    return $line | ConvertFrom-Json
}

function Invoke-ApiScript {
    param(
        [Parameter(Mandatory)] [string]$ScriptName,
        [Parameter(Mandatory)] [string[]]$ScriptArgs,
        [hashtable]$EnvOverrides = @{},
        [switch]$AllowFailure
    )
    foreach ($key in $EnvOverrides.Keys) {
        Set-Item -Path "env:$key" -Value $EnvOverrides[$key]
    }
    Push-Location $ApiDir
    if (-not (Test-Path .venv)) { python -m venv .venv }
    $env:PYTHONPATH = "."
    $output = .\.venv\Scripts\python "scripts/$ScriptName" @ScriptArgs 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0 -and -not $AllowFailure) { throw "$ScriptName failed: $output" }
    return $output.Trim()
}

function Export-DatabaseDump {
    param([Parameter(Mandatory)] [string]$Database)
    Assert-NotForbiddenDatabase -Database $Database
    $containerPath = "/tmp/phase3_dump_${Database}.sql"
    $hostPath = Join-Path $DumpsDir "${Database}.sql"
    docker exec $ContainerName sh -c "pg_dump -U $PgUser -d $Database -Fp --no-owner --no-acl -f $containerPath" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed for $Database" }
    docker cp "${ContainerName}:${containerPath}" $hostPath
    if ($LASTEXITCODE -ne 0) { throw "docker cp failed for $Database dump" }
    docker exec $ContainerName sh -c "rm -f $containerPath" | Out-Null
    if (-not (Test-Path $hostPath)) { throw "Dump file missing: $hostPath" }
    $size = (Get-Item $hostPath).Length
    if ($size -le 0) { throw "Dump file empty: $hostPath" }
    return [ordered]@{
        database = $Database
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
    Assert-NotForbiddenDatabase -Database $SourceDatabase
    $verifyDb = "recovery_verify_candidate_$($Timestamp -replace '[^0-9]','')"
    if ($verifyDb.Length -gt 63) {
        $verifyDb = "recovery_verify_$($Timestamp -replace '[^0-9]','')_$([guid]::NewGuid().ToString('N').Substring(0,8))"
    }
    Invoke-PgQuery -Database "postgres" -Sql "DROP DATABASE IF EXISTS `"$verifyDb`";" | Out-Null
    Invoke-PgQuery -Database "postgres" -Sql "CREATE DATABASE `"$verifyDb`" OWNER $PgUser;" | Out-Null
    Restore-SqlDump -TargetDatabase $verifyDb -DumpPath $DumpPath
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
    Invoke-PgQuery -Database "postgres" -Sql "DROP DATABASE IF EXISTS `"$verifyDb`";" | Out-Null
    return [ordered]@{
        source_database = $SourceDatabase
        verification_database = $verifyDb
        restore_verified = ($mismatches.Count -eq 0 -and $sourceCounts.Count -eq $verifyCounts.Count)
        source_table_count = $sourceCounts.Count
        restored_table_count = $verifyCounts.Count
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

Write-Host "Phase 3 owner candidate recovery starting."
Write-Host "Evidence root: $EvidenceRoot"
Write-Host "Phase 1 source: $Phase1EvidenceRoot"

if (-not (Test-Path $Phase1DumpPath)) {
    throw "Phase 1 validation dump not found: $Phase1DumpPath"
}
$actualSha = (Get-FileHash -Path $Phase1DumpPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha -ne $ExpectedValidationDumpSha256) {
    throw "career_os_validation dump SHA256 mismatch. expected=$ExpectedValidationDumpSha256 actual=$actualSha"
}
Add-StepLog -Step 0 -Name "verify_phase1_dump_sha256" -Detail $actualSha

$env:AAROHAN_RECOVERY_DB_IDENTITY_UUID = [guid]::NewGuid().ToString()
$env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID = [guid]::NewGuid().ToString()
$recoveryMigratePassword = New-SecurePassword
$recoveryRuntimePassword = New-SecurePassword
$candidateMigratePassword = New-SecurePassword
$candidateRuntimePassword = New-SecurePassword

$baselineKeyCounts = Get-OwnerValidationKeyRowCounts
$gitState = Get-GitState

# Step 1 — recovery staging database
Write-Host "Step 1: create $RecoveryDatabase"
Invoke-PgQuery -Database "postgres" -Sql "DROP DATABASE IF EXISTS $RecoveryDatabase;" | Out-Null
Invoke-PgQuery -Database "postgres" -Sql "CREATE DATABASE $RecoveryDatabase OWNER $PgUser;" | Out-Null
Add-StepLog -Step 1 -Name "create_recovery_database"

# Step 2 — restore Phase 1 validation snapshot
Write-Host "Step 2: restore validation snapshot into $RecoveryDatabase"
Restore-SqlDump -TargetDatabase $RecoveryDatabase -DumpPath $Phase1DumpPath
Add-StepLog -Step 2 -Name "restore_validation_snapshot" -Detail $Phase1DumpPath

# Step 3 — schema version before alembic
$schemaBeforeRecovery = Get-AlembicVersion -Database $RecoveryDatabase
Add-StepLog -Step 3 -Name "record_schema_before_alembic" -Detail $schemaBeforeRecovery

# Step 4 — alembic upgrade recovery staging
Write-Host "Step 4: alembic upgrade $RecoveryDatabase"
Invoke-AlembicUpgrade -Database $RecoveryDatabase -Purpose "RECOVERY" -IdentityUuid $env:AAROHAN_RECOVERY_DB_IDENTITY_UUID
$schemaAfterRecovery = Get-AlembicVersion -Database $RecoveryDatabase
Add-StepLog -Step 4 -Name "alembic_upgrade_recovery" -Detail "before=$schemaBeforeRecovery after=$schemaAfterRecovery"

# Step 5 — provision recovery roles
Write-Host "Step 5: provision recovery roles"
$recoveryProvision = Invoke-ProvisionStack `
    -Stack recovery `
    -Database $RecoveryDatabase `
    -Purpose "RECOVERY" `
    -IdentityUuid $env:AAROHAN_RECOVERY_DB_IDENTITY_UUID `
    -MigratePassword $recoveryMigratePassword `
    -RuntimePassword $recoveryRuntimePassword
Add-StepLog -Step 5 -Name "provision_recovery_roles"

# Step 6 — recovery identity preflight
Write-Host "Step 6: Assert-RecoveryDatabaseIdentity RECOVERY"
$recoveryIdentity = & (Join-Path $PSScriptRoot "Assert-RecoveryDatabaseIdentity.ps1") -Purpose RECOVERY -ContainerName $ContainerName -PrivilegedUser $PgUser
Add-StepLog -Step 6 -Name "assert_recovery_identity" -Detail $recoveryIdentity.IdentityFingerprint

$recoveryMigrateUrl = "postgresql+psycopg://career_os_recovery_migrate:${recoveryMigratePassword}@${HostName}:${Port}/${RecoveryDatabase}"
$recoveryRuntimeUrl = "postgresql+psycopg://career_os_recovery_runtime:${recoveryRuntimePassword}@${HostName}:${Port}/${RecoveryDatabase}"

# Step 7 — classify rows
Write-Host "Step 7: phase3_classify_rows"
$classifyOutput = Invoke-ApiScript -ScriptName "phase3_classify_rows.py" -ScriptArgs @(
    "--database-url", $recoveryMigrateUrl,
    "--output-dir", $ReportsDir
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "RECOVERY"
    AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_RECOVERY_DB_IDENTITY_UUID
}
$classificationSummary = Parse-JsonFromOutput -Text $classifyOutput
$rowRecoveryManifest = Join-Path $ReportsDir "ROW-RECOVERY-MANIFEST.json"
$rowExclusionManifest = Join-Path $ReportsDir "ROW-EXCLUSION-MANIFEST.json"
Add-StepLog -Step 7 -Name "classify_rows" -Detail ($classifyOutput)

# Step 8 — reconstruct jobs
Write-Host "Step 8: phase3_reconstruct_jobs"
$jobReconstructionPath = Join-Path $ReportsDir "JOB-RECONSTRUCTION-REPORT.json"
$reconstructOutput = Invoke-ApiScript -ScriptName "phase3_reconstruct_jobs.py" -ScriptArgs @(
    "--database-url", $recoveryMigrateUrl,
    "--classification-json", $rowRecoveryManifest,
    "--output-json", $jobReconstructionPath
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "RECOVERY"
    AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_RECOVERY_DB_IDENTITY_UUID
}
$reconstructionSummary = Parse-JsonFromOutput -Text $reconstructOutput
Add-StepLog -Step 8 -Name "reconstruct_jobs" -Detail ($reconstructOutput)

# Step 9 — owner candidate database
Write-Host "Step 9: create $CandidateDatabase"
Invoke-PgQuery -Database "postgres" -Sql "DROP DATABASE IF EXISTS $CandidateDatabase;" | Out-Null
Invoke-PgQuery -Database "postgres" -Sql "CREATE DATABASE $CandidateDatabase OWNER $PgUser;" | Out-Null
Invoke-AlembicUpgrade -Database $CandidateDatabase -Purpose "OWNER_CANDIDATE" -IdentityUuid $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID
$candidateProvision = Invoke-ProvisionStack `
    -Stack owner_candidate `
    -Database $CandidateDatabase `
    -Purpose "OWNER_CANDIDATE" `
    -IdentityUuid $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID `
    -MigratePassword $candidateMigratePassword `
    -RuntimePassword $candidateRuntimePassword
$candidateIdentity = & (Join-Path $PSScriptRoot "Assert-RecoveryDatabaseIdentity.ps1") -Purpose OWNER_CANDIDATE -ContainerName $ContainerName -PrivilegedUser $PgUser
Add-StepLog -Step 9 -Name "create_candidate_database" -Detail $candidateIdentity.IdentityFingerprint

$candidateMigrateUrl = "postgresql+psycopg://career_os_candidate_migrate:${candidateMigratePassword}@${HostName}:${Port}/${CandidateDatabase}"
$candidateRuntimeUrl = "postgresql+psycopg://career_os_candidate_runtime:${candidateRuntimePassword}@${HostName}:${Port}/${CandidateDatabase}"

# Step 10 — build candidate
Write-Host "Step 10: phase3_build_candidate"
$buildOutput = Invoke-ApiScript -ScriptName "phase3_build_candidate.py" -ScriptArgs @(
    "--source-url", $recoveryMigrateUrl,
    "--target-url", $candidateMigrateUrl,
    "--recovery-manifest", $rowRecoveryManifest,
    "--reconstruction-json", $jobReconstructionPath
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID
}
$buildSummary = Parse-JsonFromOutput -Text $buildOutput
Add-StepLog -Step 10 -Name "build_candidate" -Detail ($buildOutput)

# Step 11 — validate candidate
Write-Host "Step 11: phase3_validate_candidate"
$candidateValidationJson = Join-Path $ReportsDir "OWNER-CANDIDATE-VALIDATION.json"
$validateOutput = Invoke-ApiScript -ScriptName "phase3_validate_candidate.py" -ScriptArgs @(
    "--database-url", $candidateRuntimeUrl,
    "--output-json", $candidateValidationJson
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID
} -AllowFailure
$validationResult = Get-Content -Path $candidateValidationJson -Raw | ConvertFrom-Json
Add-StepLog -Step 11 -Name "validate_candidate" -Detail "passed=$($validationResult.passed)"

# Step 12 — backup and restore-verify candidate
Write-Host "Step 12: backup and restore-verify candidate"
$candidateDump = Export-DatabaseDump -Database $CandidateDatabase
$restoreVerify = Test-RestoreDump -SourceDatabase $CandidateDatabase -DumpPath $candidateDump.path
$backupManifest = [ordered]@{
    incident_id = $IncidentId
    timestamp = $Timestamp
    phase = 3
    source_database = $CandidateDatabase
    backup = $candidateDump
    restore_verification = $restoreVerify
    identity = [ordered]@{
        purpose = "OWNER_CANDIDATE"
        identity_uuid = $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID
        identity_fingerprint = $candidateIdentity.IdentityFingerprint
    }
    evidence_root = ($EvidenceRoot -replace '\\', '/')
}
$backupManifestPath = Join-Path $ReportsDir "OWNER-CANDIDATE-BACKUP-MANIFEST.json"
$backupManifest | ConvertTo-Json -Depth 10 | Set-Content -Path $backupManifestPath -Encoding UTF8
Add-StepLog -Step 12 -Name "backup_restore_verify" -Detail "verified=$($restoreVerify.restore_verified)"

$candidateKeyCounts = @{}
$rawCandidateCounts = docker exec $ContainerName psql -U $PgUser -d $CandidateDatabase -Atc @"
SELECT 'jobs', count(*)::text FROM jobs
UNION ALL SELECT 'applications', count(*)::text FROM applications
UNION ALL SELECT 'oauth_tokens', count(*)::text FROM oauth_tokens
UNION ALL SELECT 'users', count(*)::text FROM users
UNION ALL SELECT 'processed_gmail_messages', count(*)::text FROM processed_gmail_messages;
"@
foreach ($line in ($rawCandidateCounts -split "`n")) {
    $line = $line.Trim()
    if (-not $line) { continue }
    $parts = $line -split '\|', 2
    if ($parts.Count -eq 2) { $candidateKeyCounts[$parts[0]] = [int]$parts[1] }
}

$postKeyCounts = Get-OwnerValidationKeyRowCounts
$unchangedDiffs = Compare-KeyRowCounts -Before $baselineKeyCounts -After $postKeyCounts

# Step 13 — reports
$dataSummary = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    phase1_evidence = ($Phase1EvidenceRoot -replace '\\', '/')
    phase1_dump_sha256 = $actualSha
    recovery_database = $RecoveryDatabase
    candidate_database = $CandidateDatabase
    schema_before_recovery_upgrade = $schemaBeforeRecovery
    schema_after_recovery_upgrade = $schemaAfterRecovery
    classification_summary = $classificationSummary
    reconstruction_summary = $reconstructionSummary
    import_summary = $buildSummary
    validation = $validationResult
    candidate_key_row_counts = $candidateKeyCounts
    owner_validation_unchanged = ($unchangedDiffs.Count -eq 0)
    owner_validation_diffs = $unchangedDiffs
}
$dataSummaryPath = Join-Path $ReportsDir "OWNER-CANDIDATE-DATA-SUMMARY.json"
$dataSummary | ConvertTo-Json -Depth 12 | Set-Content -Path $dataSummaryPath -Encoding UTF8

$defectLines = if ($validationResult.defects.Count) {
    ($validationResult.defects | ForEach-Object { "- [$($_.severity)] $($_.check): $($_.detail)" }) -join "`n"
} else { "- none" }

$validationReport = @"
# Owner Candidate Validation Report

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")
Evidence root: ``$($EvidenceRoot -replace '\\','/')``

## Result

- Validation passed: **$($validationResult.passed)**
- Defect count: $($validationResult.defects.Count)

## Checks

$(($validationResult.checks.PSObject.Properties | ForEach-Object { "- $($_.Name): $($_.Value)" }) -join "`n")

## Defects

$defectLines

## Candidate key row counts

$(($candidateKeyCounts.GetEnumerator() | Sort-Object Name | ForEach-Object { "- $($_.Key): $($_.Value)" }) -join "`n")

## Owner / validation unchanged

- career_os and career_os_validation key tables unchanged: $($unchangedDiffs.Count -eq 0)
"@
$validationReportPath = Join-Path $ReportsDir "OWNER-CANDIDATE-VALIDATION-REPORT.md"
Set-Content -Path $validationReportPath -Value $validationReport -Encoding UTF8

$cutoverPlan = @"
# Owner Candidate Cutover Plan

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")

## Status

**NOT EXECUTED** — Phase 3 stops before canonical owner cutover.

## Preconditions

1. Owner reviews ``OWNER-CANDIDATE-VALIDATION-REPORT.md`` and ``OWNER-CANDIDATE-DATA-SUMMARY.json``.
2. Ambiguous rows in ``AMBIGUOUS-ROWS-REPORT.md`` are dispositioned.
3. Verified backup exists: ``OWNER-CANDIDATE-BACKUP-MANIFEST.json`` (restore_verified=$($restoreVerify.restore_verified)).
4. Owner issues explicit approval phrase: ``APPROVE OWNER CANDIDATE CUTOVER``.

## Proposed cutover sequence (Gate 2 — manual only)

1. Stop owner API traffic.
2. Take a fresh verified owner backup (``Invoke-VerifiedOwnerBackup.ps1``).
3. Record owner identity fingerprint and row counts.
4. Redirect owner runtime to ``$CandidateDatabase`` credentials (new migrate/runtime roles).
5. Re-run owner identity preflight against promoted database.
6. Smoke-test login, OAuth metadata, Gmail idempotency, applications, Fresh Jobs.
7. Update recovery state to post-cutover and proceed to Phase 4 validation.

## Databases after cutover

| Database | Role |
|---|---|
| career_os | Pre-cutover contaminated owner (retain for rollback window) |
| career_os_owner_candidate | Promoted owner runtime target |
| career_os_recovery | Staging evidence (retain until Phase 4 GO) |
| career_os_validation | Untouched recovery source evidence |
"@
$cutoverPlanPath = Join-Path $ReportsDir "OWNER-CANDIDATE-CUTOVER-PLAN.md"
Set-Content -Path $cutoverPlanPath -Value $cutoverPlan -Encoding UTF8

$rollbackPlan = @"
# Owner Candidate Rollback Plan

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")

## If cutover has NOT occurred (current Phase 3 state)

1. Drop staging databases when evidence is archived:
   - ``DROP DATABASE IF EXISTS $RecoveryDatabase;``
   - ``DROP DATABASE IF EXISTS $CandidateDatabase;``
2. Retain artifacts under ``$($EvidenceRoot -replace '\\','/')``.
3. Canonical owner remains ``career_os`` — no runtime change required.

## If cutover occurred and rollback is required

1. Stop owner API.
2. Restore last verified pre-cutover owner backup into ``career_os`` (owner approval required).
3. Re-provision owner migrate/runtime roles and re-validate owner identity marker.
4. Drop or quarantine ``$CandidateDatabase`` after rollback verification.
5. Document incident in recovery state file.

## Evidence for rollback

- Phase 1 snapshot: ``$($Phase1EvidenceRoot -replace '\\','/')``
- Phase 3 candidate backup: ``$($candidateDump.path -replace '\\','/')`` (sha256=$($candidateDump.sha256))
- Pre-cutover owner backup manifest (to be captured at Gate 2)
"@
$rollbackPlanPath = Join-Path $ReportsDir "OWNER-CANDIDATE-ROLLBACK-PLAN.md"
Set-Content -Path $rollbackPlanPath -Value $rollbackPlan -Encoding UTF8

$defectRegister = @"
# Owner Candidate Defect Register — Phase 3

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")

| ID | Severity | Check | Detail | Disposition |
|---|---|---|---|---|
$(if ($validationResult.defects.Count) {
    $i = 1
    ($validationResult.defects | ForEach-Object {
        "| P3-DEF-$('{0:D3}' -f $i) | $($_.severity) | $($_.check) | $($_.detail) | open |"
        $i++
    }) -join "`n"
} else {
    "| — | — | — | No defects recorded | — |"
})

## Notes

- Defects sourced from ``phase3_validate_candidate.py`` output.
- Ambiguous rows excluded from import are tracked separately in ``AMBIGUOUS-ROWS-REPORT.md``.
- Cutover blocked until Critical/High defects are resolved or explicitly accepted by owner.
"@
$defectRegisterPath = Join-Path $ReportsDir "OWNER-CANDIDATE-DEFECT-REGISTER.md"
Set-Content -Path $defectRegisterPath -Value $defectRegister -Encoding UTF8

$executionReport = @"
# Phase 3 Execution Report — owner-db-incident-20260709

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")
Timestamp: ``$Timestamp``
Evidence root: ``$($EvidenceRoot -replace '\\','/')``

## Git

- Branch: $($gitState.branch)
- SHA: $($gitState.sha)

## Phase 1 source

- Dump: ``$($Phase1DumpPath -replace '\\','/')``
- SHA256 verified: $actualSha

## Execution steps

$(($ExecutionLog | ForEach-Object { "- Step $($_.step) $($_.name): $($_.status) $(if ($_.detail) { "($($_.detail))" })" }) -join "`n")

## Databases

| Database | Purpose | Identity UUID |
|---|---|---|
| $RecoveryDatabase | RECOVERY | $($env:AAROHAN_RECOVERY_DB_IDENTITY_UUID) |
| $CandidateDatabase | OWNER_CANDIDATE | $($env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID) |

## Owner / validation protection

| Database | Unchanged |
|---|---|
| career_os | $(if ($unchangedDiffs | Where-Object database -eq 'career_os') { 'NO' } else { 'YES' }) |
| career_os_validation | $(if ($unchangedDiffs | Where-Object database -eq 'career_os_validation') { 'NO' } else { 'YES' }) |

## Candidate validation

- Passed: $($validationResult.passed)
- Backup restore verified: $($restoreVerify.restore_verified)

## Evidence files

- ``$($dataSummaryPath -replace '\\','/')``
- ``$($validationReportPath -replace '\\','/')``
- ``$($cutoverPlanPath -replace '\\','/')``
- ``$($rollbackPlanPath -replace '\\','/')``
- ``$($defectRegisterPath -replace '\\','/')``
- ``$($backupManifestPath -replace '\\','/')``
- ``$($rowRecoveryManifest -replace '\\','/')``
- ``$($rowExclusionManifest -replace '\\','/')``
- ``$($jobReconstructionPath -replace '\\','/')``

## Gate

**STOP** — canonical owner cutover not performed. Await Gate 2 owner approval.
"@
$executionReportPath = Join-Path $ReportsDir "PHASE-3-EXECUTION-REPORT.md"
Set-Content -Path $executionReportPath -Value $executionReport -Encoding UTF8
Add-StepLog -Step 13 -Name "write_reports"

# Step 14 — identities (no passwords)
$identities = [ordered]@{
    incident_id = $IncidentId
    timestamp = $Timestamp
    recovery = [ordered]@{
        purpose = "RECOVERY"
        database = $RecoveryDatabase
        identity_uuid = $env:AAROHAN_RECOVERY_DB_IDENTITY_UUID
        identity_fingerprint = $recoveryIdentity.IdentityFingerprint
        migrate_role = "career_os_recovery_migrate"
        runtime_role = "career_os_recovery_runtime"
    }
    owner_candidate = [ordered]@{
        purpose = "OWNER_CANDIDATE"
        database = $CandidateDatabase
        identity_uuid = $env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID
        identity_fingerprint = $candidateIdentity.IdentityFingerprint
        migrate_role = "career_os_candidate_migrate"
        runtime_role = "career_os_candidate_runtime"
    }
    owner_validation_unchanged = ($unchangedDiffs.Count -eq 0)
    cutover_performed = $false
}
$identitiesPath = Join-Path $ReportsDir "PHASE-3-IDENTITIES.json"
$identities | ConvertTo-Json -Depth 6 | Set-Content -Path $identitiesPath -Encoding UTF8
Add-StepLog -Step 14 -Name "write_identities"

# Step 15 — secrets (gitignored under artifacts)
$secrets = [ordered]@{
    incident_id = $IncidentId
    timestamp = $Timestamp
    recovery = [ordered]@{
        migrate_password = $recoveryMigratePassword
        runtime_password = $recoveryRuntimePassword
        migrate_url = $recoveryMigrateUrl
        runtime_url = $recoveryRuntimeUrl
    }
    owner_candidate = [ordered]@{
        migrate_password = $candidateMigratePassword
        runtime_password = $candidateRuntimePassword
        migrate_url = $candidateMigrateUrl
        runtime_url = $candidateRuntimeUrl
    }
    warning = "Local recovery secrets — never commit. artifacts/ is gitignored."
}
$secretsPath = Join-Path $ReportsDir "phase3-secrets.local.json"
$secrets | ConvertTo-Json -Depth 6 | Set-Content -Path $secretsPath -Encoding UTF8
Add-StepLog -Step 15 -Name "write_secrets"

if (-not $restoreVerify.restore_verified) {
    throw "Candidate backup restore verification failed"
}
if ($unchangedDiffs.Count -gt 0) {
    throw "Owner or validation key row counts changed during Phase 3: $($unchangedDiffs | ConvertTo-Json -Compress)"
}
if (-not $validationResult.passed) {
    throw "Owner candidate validation failed — see $validationReportPath"
}

Write-Host ""
Write-Host "Phase 3 complete. Evidence: $EvidenceRoot"
Write-Host "Execution report: $executionReportPath"
Write-Host "Cutover NOT performed — await Gate 2 owner approval."

return [ordered]@{
    timestamp = $Timestamp
    evidence_root = $EvidenceRoot
    execution_report = $executionReportPath
    validation_passed = $validationResult.passed
    owner_validation_unchanged = ($unchangedDiffs.Count -eq 0)
    cutover_performed = $false
}
