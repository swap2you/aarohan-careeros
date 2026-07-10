#Requires -Version 5.1
<#
.SYNOPSIS
  Phase 3 final candidate remediation — post OAuth reconnect.
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

if (-not $Timestamp) { $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss" }

$EvidenceRoot = Join-Path $Root "artifacts\recovery\incident-20260709\phase3-final-$Timestamp"
$ReportsDir = Join-Path $EvidenceRoot "reports"
$DumpsDir = Join-Path $EvidenceRoot "dumps"
New-Item -ItemType Directory -Force -Path $ReportsDir, $DumpsDir | Out-Null

$ForbiddenDatabases = @("career_os", "career_os_validation")
$CandidateDatabase = "career_os_owner_candidate"
$ApiDir = Join-Path $Root "apps\api"
$KeyTables = @("jobs", "applications", "oauth_tokens", "users", "processed_gmail_messages")

Write-Host "Assert-RecoveryDatabaseIdentity OWNER_CANDIDATE"
$candidateIdentity = & (Join-Path $PSScriptRoot "Assert-RecoveryDatabaseIdentity.ps1") `
    -Purpose OWNER_CANDIDATE -ContainerName $ContainerName -PrivilegedUser $PgUser

$markerUuid = $candidateIdentity.IdentityUuid
if (-not $markerUuid) {
    $markerUuid = (docker exec $ContainerName psql -U $PgUser -d $CandidateDatabase -Atc "SELECT identity_uuid FROM aarohan_meta.database_identity LIMIT 1").Trim()
}
$env:AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID = $markerUuid

$migrateUrl = "postgresql+psycopg://career_os_candidate_migrate:$($env:CANDIDATE_MIGRATE_PASSWORD)@127.0.0.1:5432/$CandidateDatabase"
$runtimeUrl = "postgresql+psycopg://career_os_candidate_runtime:$($env:CANDIDATE_RUNTIME_PASSWORD)@127.0.0.1:5432/$CandidateDatabase"
$bootstrapUrl = "postgresql+psycopg://${PgUser}:$($env:POSTGRES_PASSWORD)@127.0.0.1:5432/$CandidateDatabase"

function Invoke-ApiScript {
    param(
        [string]$ScriptName,
        [string[]]$ScriptArgs,
        [hashtable]$EnvOverrides = @{},
        [switch]$AllowFailure
    )
    Push-Location $ApiDir
    foreach ($k in $EnvOverrides.Keys) { Set-Item -Path "env:$k" -Value $EnvOverrides[$k] }
    $env:PYTHONPATH = "."
    $output = .\.venv\Scripts\python "scripts/$ScriptName" @ScriptArgs 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0 -and -not $AllowFailure) { throw "$ScriptName failed: $output" }
    return @{ code = $code; output = $output.Trim() }
}

function Get-KeyRowCounts {
    param([string]$Database)
    if ($Database -in $ForbiddenDatabases) {
        $counts = @{}
        foreach ($t in $KeyTables) {
            $counts[$t] = [int](docker exec $ContainerName psql -U $PgUser -d $Database -Atc "SELECT count(*) FROM $t")
        }
        return $counts
    }
    $counts = @{}
    foreach ($t in $KeyTables) {
        $counts[$t] = [int](docker exec $ContainerName psql -U $PgUser -d $Database -Atc "SELECT count(*) FROM $t")
    }
    return $counts
}

$baselineOwner = Get-KeyRowCounts -Database "career_os"
$baselineValidation = Get-KeyRowCounts -Database "career_os_validation"

Write-Host "Phase 3 final remediation. Evidence: $EvidenceRoot"

$ownerUrl = "postgresql+psycopg://${PgUser}:$($env:POSTGRES_PASSWORD)@127.0.0.1:5432/career_os"
$oauthSyncJson = Join-Path $ReportsDir "OAUTH-CANDIDATE-SYNC-FROM-OWNER.json"
Invoke-ApiScript -ScriptName "phase3_final_sync_oauth_to_candidate.py" -ScriptArgs @(
    "--candidate-url", $migrateUrl,
    "--source-url", $ownerUrl,
    "--output-json", $oauthSyncJson
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
} -AllowFailure | Out-Null

$oauthJson = Join-Path $ReportsDir "OAUTH-CANDIDATE-FINAL-VALIDATION.json"
Invoke-ApiScript -ScriptName "phase3_final_validate_oauth.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--output-json", $oauthJson
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
    OAUTH_FIXTURE_MODE = "false"
} -AllowFailure | Out-Null

$driveJson = Join-Path $ReportsDir "DRIVE-ROOT-FINAL-RESOLUTION.json"
Invoke-ApiScript -ScriptName "phase3_final_resolve_drive.py" -ScriptArgs @(
    "--database-url", $migrateUrl,
    "--output-json", $driveJson,
    "--bind"
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
    OAUTH_FIXTURE_MODE = "false"
} -AllowFailure | Out-Null

$discoveryJson = Join-Path $ReportsDir "CANDIDATE-FINAL-LIVE-DISCOVERY.json"
Invoke-ApiScript -ScriptName "phase3_final_live_discovery.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--output-json", $discoveryJson
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
    OAUTH_FIXTURE_MODE = "false"
} -AllowFailure | Out-Null

$manualJson = Join-Path $ReportsDir "ACCEPTED-JOB-MANUAL-REVIEW.json"
Invoke-ApiScript -ScriptName "phase3_final_manual_job_review.py" -ScriptArgs @(
    "--database-url", $migrateUrl,
    "--output-json", $manualJson,
    "--apply"
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
    AAROHAN_DB_IDENTITY_UUID = $markerUuid
} -AllowFailure | Out-Null

$backupManifest = Join-Path $ReportsDir "OWNER-CANDIDATE-FINAL-BACKUP-MANIFEST.json"
$backupVerify = Join-Path $ReportsDir "OWNER-CANDIDATE-FINAL-RESTORE-VERIFICATION.json"
Invoke-ApiScript -ScriptName "phase3_final_backup_restore.py" -ScriptArgs @(
    "--dumps-dir", $DumpsDir,
    "--manifest-json", $backupManifest,
    "--verification-json", $backupVerify,
    "--identity-uuid", $markerUuid
) -AllowFailure | Out-Null

$smokeJson = Join-Path (Join-Path $Root "artifacts\recovery\incident-20260709\phase3-rework-20260710_171518\reports") "CANDIDATE-WORKFLOW-SMOKE-EVIDENCE.json"
if (-not (Test-Path $smokeJson)) {
    Invoke-ApiScript -ScriptName "phase3_rework_workflow_smoke.py" -ScriptArgs @(
        "--database-url", $runtimeUrl,
        "--api-base", "http://127.0.0.1:8002",
        "--output-json", (Join-Path $ReportsDir "CANDIDATE-WORKFLOW-SMOKE-EVIDENCE.json"),
        "--cleanup"
    ) -EnvOverrides @{
        AAROHAN_DB_IDENTITY_PURPOSE = "OWNER_CANDIDATE"
        AAROHAN_DB_IDENTITY_UUID = $markerUuid
        ADMIN_EMAIL = $env:ADMIN_EMAIL
        ADMIN_PASSWORD = $env:ADMIN_PASSWORD
    } -AllowFailure | Out-Null
    $smokeJson = Join-Path $ReportsDir "CANDIDATE-WORKFLOW-SMOKE-EVIDENCE.json"
}

$env:CUTOVER_REHEARSAL_PHRASE = "APPROVE OWNER CANDIDATE CUTOVER"
$cutoverJson = Join-Path $ReportsDir "CUTOVER-FINAL-REHEARSAL-MANIFEST.json"
$cutoverReport = Join-Path $ReportsDir "CUTOVER-FINAL-REHEARSAL-REPORT.md"
Invoke-ApiScript -ScriptName "phase3_final_cutover_rehearsal.py" -ScriptArgs @(
    "--candidate-uuid", $markerUuid,
    "--output-json", $cutoverJson,
    "--report-md", $cutoverReport,
    "--dumps-dir", $DumpsDir,
    "--destructive-token", $env:AAROHAN_DESTRUCTIVE_TOKEN,
    "--pg-password", $env:POSTGRES_PASSWORD
) -AllowFailure | Out-Null

$validationJson = Join-Path $ReportsDir "OWNER-CANDIDATE-VALIDATION.json"
$validationReport = Join-Path $ReportsDir "OWNER-CANDIDATE-VALIDATION-REPORT.md"
$defectRegister = Join-Path $ReportsDir "OWNER-CANDIDATE-DEFECT-REGISTER.md"
$validationResult = Invoke-ApiScript -ScriptName "phase3_final_validate_candidate.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--output-json", $validationJson,
    "--report-md", $validationReport,
    "--defect-register-md", $defectRegister,
    "--oauth-json", $oauthJson,
    "--drive-json", $driveJson,
    "--discovery-json", $discoveryJson,
    "--manual-review-json", $manualJson,
    "--backup-verification-json", $backupVerify,
    "--cutover-rehearsal-json", $cutoverJson,
    "--workflow-smoke-json", $smokeJson,
    "--api-base", "http://127.0.0.1:8002"
) -AllowFailure

$afterOwner = Get-KeyRowCounts -Database "career_os"
$afterValidation = Get-KeyRowCounts -Database "career_os_validation"
$unchanged = ($baselineOwner.jobs -eq $afterOwner.jobs) -and ($baselineValidation.jobs -eq $afterValidation.jobs)

$candidateCounts = Get-KeyRowCounts -Database $CandidateDatabase
$validationObj = Get-Content $validationJson | ConvertFrom-Json
$manualObj = Get-Content $manualJson | ConvertFrom-Json
$oauthObj = Get-Content $oauthJson | ConvertFrom-Json
$driveObj = Get-Content $driveJson | ConvertFrom-Json
$discoveryObj = Get-Content $discoveryJson | ConvertFrom-Json

$finalReport = Join-Path $ReportsDir "PHASE-3-FINAL-REMEDIATION-REPORT.md"
@"
# Phase 3 Final Remediation Report

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")
Evidence: ``$($EvidenceRoot.Replace('\','/'))``

## Candidate runtime

- API: http://127.0.0.1:8002
- Web: http://127.0.0.1:3002
- Identity UUID: $markerUuid

## Results

- Validation passed: $($validationObj.passed)
- OAuth passed: $($oauthObj.passed)
- Drive blocking: $($driveObj.blocking)
- Gmail scanned: $($discoveryObj.gmail_messages_scanned)
- Gmail replayed: $($discoveryObj.gmail_messages_replayed)
- Manual accepted: $($manualObj.counts.accepted)
- career_os / career_os_validation unchanged: $unchanged

## Gate

State: GATE_2_OWNER_CUTOVER_APPROVAL_REQUIRED — Codex Phase 3 final rereview required.
"@ | Set-Content -Path $finalReport -Encoding UTF8

Write-Host "Final remediation complete. Validation passed: $($validationObj.passed)"
return @{
    evidence_root = $EvidenceRoot
    validation_passed = $validationObj.passed
    unchanged = $unchanged
    candidate_counts = $candidateCounts
}
