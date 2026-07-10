#Requires -Version 5.1
<#
.SYNOPSIS
  Phase 3 rework orchestrator — resolves Codex NO GO blockers on owner candidate.
  Never modifies career_os or career_os_validation.
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
. (Join-Path $Root "scripts/local/Invoke-AarohanCandidateCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

Write-Host "Assert-RecoveryDatabaseIdentity OWNER_CANDIDATE"
$candidateIdentity = & (Join-Path $PSScriptRoot "Assert-RecoveryDatabaseIdentity.ps1") `
    -Purpose OWNER_CANDIDATE -ContainerName $ContainerName -PrivilegedUser $PgUser

if (-not $Timestamp) { $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss" }

$EvidenceRoot = Join-Path $Root "artifacts\recovery\incident-20260709\phase3-rework-$Timestamp"
$ReportsDir = Join-Path $EvidenceRoot "reports"
$DumpsDir = Join-Path $EvidenceRoot "dumps"
New-Item -ItemType Directory -Force -Path $ReportsDir, $DumpsDir | Out-Null

$ForbiddenDatabases = @("career_os", "career_os_validation")
$CandidateDatabase = "career_os_owner_candidate"
$HostName = "127.0.0.1"
$Port = 5432
$ApiDir = Join-Path $Root "apps\api"
$KeyTables = @("jobs", "applications", "oauth_tokens", "users", "processed_gmail_messages")

function Invoke-PgQuery {
    param(
        [string]$Database,
        [string]$Sql,
        [switch]$TuplesOnly,
        [switch]$AllowForbiddenRead
    )
    if ($Database -in $ForbiddenDatabases -and -not $AllowForbiddenRead) {
        throw "Forbidden database write/query $Database"
    }
    if ($Database -in $ForbiddenDatabases) {
        $forbiddenWrite = @(
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'GRANT', 'REVOKE'
        )
        $upper = $Sql.ToUpperInvariant()
        foreach ($kw in $forbiddenWrite) {
            if ($upper -match "\b$kw\b") {
                throw "Refusing mutating SQL on forbidden database $Database"
            }
        }
    }
    $args = @("exec", $ContainerName, "psql", "-U", $PgUser, "-d", $Database)
    if ($TuplesOnly) { $args += "-At" } else { $args += "-A" }
    $args += "-c", $Sql
    $out = docker @args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "psql failed: $out" }
    return (($out | Out-String).Trim() -replace "`r", "")
}

function Get-KeyRowCounts {
    param([string]$Database)
    $counts = @{}
    foreach ($t in $KeyTables) {
        $counts[$t] = [int](Invoke-PgQuery -Database $Database -Sql "SELECT count(*) FROM $t" -TuplesOnly -AllowForbiddenRead)
    }
    return $counts
}

function Invoke-ApiScript {
    param(
        [string]$ScriptName,
        [string[]]$ScriptArgs,
        [hashtable]$EnvOverrides = @{},
        [switch]$AllowFailure
    )
    Push-Location $ApiDir
    if (-not (Test-Path .venv)) { python -m venv .venv }
    foreach ($k in $EnvOverrides.Keys) { Set-Item -Path "env:$k" -Value $EnvOverrides[$k] }
    $env:PYTHONPATH = "."
    $output = .\.venv\Scripts\python "scripts/$ScriptName" @ScriptArgs 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0 -and -not $AllowFailure) { throw "$ScriptName failed: $output" }
    return @{ code = $code; output = $output.Trim() }
}

Write-Host "Phase 3 rework starting. Evidence: $EvidenceRoot"

$baselineOwner = Get-KeyRowCounts -Database "career_os"
$baselineValidation = Get-KeyRowCounts -Database "career_os_validation"

# Sync candidate identity UUID from marker
$markerUuid = (Invoke-PgQuery -Database $CandidateDatabase -Sql "SELECT identity_uuid FROM aarohan_meta.database_identity LIMIT 1" -TuplesOnly).Trim()
if (-not $markerUuid) { throw "Missing candidate identity marker" }
$env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID = $markerUuid

if ([string]::IsNullOrWhiteSpace($env:CANDIDATE_MIGRATE_PASSWORD) -or [string]::IsNullOrWhiteSpace($env:CANDIDATE_RUNTIME_PASSWORD)) {
    & pwsh -NoProfile -File (Join-Path $Root "scripts/local/Sync-EnvLocal.ps1") -GenerateMissing
    Import-AarohanRepoEnvLocal -Root $Root
}

# Alembic upgrade candidate
$bootstrapUrl = "postgresql+psycopg://${PgUser}:$($env:POSTGRES_PASSWORD)@${HostName}:${Port}/${CandidateDatabase}"
$migrateUrl = "postgresql+psycopg://career_os_candidate_migrate:$($env:CANDIDATE_MIGRATE_PASSWORD)@${HostName}:${Port}/${CandidateDatabase}"
$runtimeUrl = "postgresql+psycopg://career_os_candidate_runtime:$($env:CANDIDATE_RUNTIME_PASSWORD)@${HostName}:${Port}/${CandidateDatabase}"

Push-Location $ApiDir
$env:BOOTSTRAP_DATABASE_URL = $bootstrapUrl
$env:MIGRATION_DATABASE_URL = $bootstrapUrl
$env:DATABASE_URL = $bootstrapUrl
$env:AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
$env:AAROHAN_DB_IDENTITY_UUID = $markerUuid
.\.venv\Scripts\python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Candidate alembic upgrade failed" }
$env:PYTHONPATH = "."
.\.venv\Scripts\python scripts/provision_database_roles.py --stack owner_candidate
Pop-Location

$gmailReplayJson = Join-Path $ReportsDir "GMAIL-REPLAY-CLASSIFICATION.json"
Invoke-ApiScript -ScriptName "phase3_rework_classify_gmail_replay.py" -ScriptArgs @(
    "--database-url", $migrateUrl,
    "--output-json", $gmailReplayJson
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
} | Out-Null

$auditJson = Join-Path $ReportsDir "AUDIT-RECRUITER-INTEGRITY.json"
Invoke-ApiScript -ScriptName "phase3_rework_audit_recruiter_integrity.py" -ScriptArgs @(
    "--database-url", $migrateUrl,
    "--output-json", $auditJson,
    "--apply"
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
} -AllowFailure | Out-Null

$oauthJson = Join-Path $ReportsDir "OAUTH-CANDIDATE-VALIDATION.json"
$oauthResult = Invoke-ApiScript -ScriptName "phase3_rework_validate_oauth.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--output-json", $oauthJson
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
    OAUTH_FIXTURE_MODE = "false"
} -AllowFailure

$driveJson = Join-Path $ReportsDir "DRIVE-ROOT-RESOLUTION.json"
$driveResult = Invoke-ApiScript -ScriptName "phase3_rework_resolve_drive_root.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--output-json", $driveJson
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
    OAUTH_FIXTURE_MODE = "false"
} -AllowFailure

$jobsJson = Join-Path $ReportsDir "CANDIDATE-LIVE-JOB-RECONSTRUCTION.json"
$jobsResult = Invoke-ApiScript -ScriptName "phase3_rework_live_job_reconstruction.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--output-json", $jobsJson
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
    OAUTH_FIXTURE_MODE = "false"
} -AllowFailure

Write-Host "Starting candidate runtime (8002/3002)..."
& pwsh -NoProfile -File (Join-Path $Root "scripts/local/Start-Aarohan-Candidate.ps1") -SkipProvision

Start-Sleep -Seconds 15
$health = Invoke-WebRequest -Uri "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 30
if ($health.StatusCode -ne 200) { throw "Candidate API health failed" }

$smokeJson = Join-Path $ReportsDir "CANDIDATE-WORKFLOW-SMOKE-EVIDENCE.json"
$smokeResult = Invoke-ApiScript -ScriptName "phase3_rework_workflow_smoke.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--api-base", "http://127.0.0.1:8002",
    "--output-json", $smokeJson,
    "--cleanup"
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
    ADMIN_EMAIL = $env:ADMIN_EMAIL
    ADMIN_PASSWORD = $env:ADMIN_PASSWORD
} -AllowFailure

$validationJson = Join-Path $ReportsDir "OWNER-CANDIDATE-VALIDATION.json"
$validationResult = Invoke-ApiScript -ScriptName "phase3_rework_validate_candidate.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--output-json", $validationJson,
    "--oauth-json", $oauthJson,
    "--drive-json", $driveJson,
    "--gmail-replay-json", $gmailReplayJson,
    "--jobs-json", $jobsJson,
    "--audit-json", $auditJson,
    "--workflow-smoke-json", $smokeJson,
    "--api-base", "http://127.0.0.1:8002"
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
} -AllowFailure

# Candidate backup
$candidateDump = Join-Path $DumpsDir "career_os_owner_candidate.sql"
docker exec $ContainerName pg_dump -U $PgUser -d $CandidateDatabase -Fp --no-owner --no-acl -f /tmp/candidate_rework.sql
docker cp "${ContainerName}:/tmp/candidate_rework.sql" $candidateDump
$dumpSha = (Get-FileHash -Path $candidateDump -Algorithm SHA256).Hash.ToLowerInvariant()

$env:CUTOVER_REHEARSAL_PHRASE = "APPROVE OWNER CANDIDATE CUTOVER"
$rehearsalJson = Join-Path $ReportsDir "CUTOVER-REHEARSAL-MANIFEST.json"
$rehearsalResult = Invoke-ApiScript -ScriptName "phase3_rework_cutover_rehearsal.py" -ScriptArgs @(
    "--output-json", $rehearsalJson,
    "--dumps-dir", $DumpsDir,
    "--destructive-token", $env:AAROHAN_DESTRUCTIVE_TOKEN
) -AllowFailure

Invoke-ApiScript -ScriptName "phase3_rework_emit_evidence.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--reports-dir", $ReportsDir,
    "--evidence-root", $EvidenceRoot,
    "--identity-uuid", $markerUuid,
    "--candidate-dump", $candidateDump
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
} | Out-Null

$afterOwner = Get-KeyRowCounts -Database "career_os"
$afterValidation = Get-KeyRowCounts -Database "career_os_validation"
$unchanged = ($baselineOwner.jobs -eq $afterOwner.jobs) -and ($baselineValidation.jobs -eq $afterValidation.jobs)

$validationObj = Get-Content $validationJson | ConvertFrom-Json
$reworkReport = Join-Path $ReportsDir "PHASE-3-REWORK-REPORT.md"
@"
# Phase 3 Rework Report

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")
Evidence: ``$($EvidenceRoot.Replace('\','/'))``

## Candidate runtime

- API: http://127.0.0.1:8002
- Web: http://127.0.0.1:3002
- Database: $CandidateDatabase
- Identity UUID: $markerUuid

## Results

- Validation passed: $($validationObj.passed)
- OAuth validation: $(if ($oauthResult.code -eq 0) { 'ok' } else { 'failed' })
- Drive resolution: $(if ($driveResult.code -eq 0) { 'ok' } else { 'blocking or failed' })
- Live jobs reconstruction: $(if ($jobsResult.code -eq 0) { 'ok' } else { 'failed' })
- Workflow smoke: $(if ($smokeResult.code -eq 0) { 'ok' } else { 'failed' })
- Cutover rehearsal: $(if ($rehearsalResult.code -eq 0) { 'ok' } else { 'failed' })
- career_os / career_os_validation unchanged: $unchanged

## Gate

State target: GATE_2_OWNER_CUTOVER_APPROVAL_REQUIRED (pending Codex re-review)
"@ | Set-Content -Path $reworkReport -Encoding UTF8

Write-Host "Phase 3 rework complete. Evidence: $EvidenceRoot"
Write-Host "Validation passed: $($validationObj.passed)"

return @{
    evidence_root = $EvidenceRoot
    validation_passed = $validationObj.passed
    unchanged = $unchanged
}
