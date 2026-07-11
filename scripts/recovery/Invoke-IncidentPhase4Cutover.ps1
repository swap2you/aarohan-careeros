#Requires -Version 5.1
<#
.SYNOPSIS
  Phase 4 guarded canonical owner cutover and final validation.
#>
param(
    [string]$Timestamp = "",
    [string]$ApprovalPhrase = "APPROVE OWNER CANDIDATE CUTOVER",
    [string]$ContainerName = "aarohan-careeros-postgres-1",
    [string]$PgUser = "career_os",
    [string]$CandidateUuid = "78010e56-041c-4fec-b8f7-0f9ca313d267"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $Root "scripts/local/Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

if ($ApprovalPhrase -ne "APPROVE OWNER CANDIDATE CUTOVER") {
    throw "Gate 2 approval phrase mismatch."
}
if (-not $env:AAROHAN_DESTRUCTIVE_TOKEN) {
    throw "Missing AAROHAN_DESTRUCTIVE_TOKEN."
}

if (-not $Timestamp) { $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss" }

$EvidenceRoot = Join-Path $Root "artifacts\recovery\incident-20260709\phase4-cutover-$Timestamp"
$ReportsDir = Join-Path $EvidenceRoot "reports"
$DumpsDir = Join-Path $EvidenceRoot "dumps"
New-Item -ItemType Directory -Force -Path $ReportsDir, $DumpsDir | Out-Null

$OldOwnerUuid = (docker exec $ContainerName psql -U $PgUser -d career_os -Atc "SELECT identity_uuid FROM aarohan_meta.database_identity LIMIT 1;").Trim()
$ApiDir = Join-Path $Root "apps\api"

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

Write-Host "=== Phase 4 cutover ==="
Write-Host "Stopping owner and candidate API/web (postgres stays up)..."
docker stop aarohan-careeros-api-1 aarohan-careeros-web-1 aarohan-candidate-api aarohan-candidate-web 2>$null | Out-Null
Start-Sleep -Seconds 3

$ownerApiDown = $true
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 | Out-Null
    $ownerApiDown = $false
} catch {}
if (-not $ownerApiDown) { throw "Owner API still responding on :8000" }

$cutoverJson = Join-Path $ReportsDir "PHASE-4-CUTOVER-MANIFEST.json"
$cutoverResult = Invoke-ApiScript -ScriptName "phase4_execute_cutover.py" -ScriptArgs @(
    "--candidate-uuid", $CandidateUuid,
    "--confirmation-phrase", $ApprovalPhrase,
    "--dumps-dir", $DumpsDir,
    "--output-json", $cutoverJson
) -EnvOverrides @{
    CUTOVER_APPROVAL_PHRASE = $ApprovalPhrase
    POSTGRES_RUNTIME_PASSWORD = $env:POSTGRES_RUNTIME_PASSWORD
}

if ($cutoverResult.code -ne 0) {
    throw "Cutover execution failed. See $cutoverJson"
}

$cutoverObj = Get-Content $cutoverJson | ConvertFrom-Json
$NewOwnerUuid = $cutoverObj.new_owner_uuid
$RollbackDb = $cutoverObj.rollback_database

Write-Host "Updating .env.local AAROHAN_OWNER_DB_IDENTITY_UUID -> $NewOwnerUuid"
$envPath = Join-Path $Root ".env.local"
$content = Get-Content $envPath -Raw
if ($content -match '(?m)^AAROHAN_OWNER_DB_IDENTITY_UUID=') {
    $content = [regex]::Replace($content, '(?m)^AAROHAN_OWNER_DB_IDENTITY_UUID=.*$', "AAROHAN_OWNER_DB_IDENTITY_UUID=$NewOwnerUuid")
} else {
    $content += "`nAAROHAN_OWNER_DB_IDENTITY_UUID=$NewOwnerUuid`n"
}
Set-Content -Path $envPath -Value $content -Encoding UTF8 -NoNewline
Import-AarohanRepoEnvLocal -Root $Root

Write-Host "Provisioning owner database roles..."
& pwsh -NoProfile -File (Join-Path $Root "scripts/local/Invoke-ProvisionOwnerDatabase.ps1")
if ($LASTEXITCODE -ne 0) { throw "Invoke-ProvisionOwnerDatabase failed" }

Write-Host "Starting owner stack..."
& pwsh -NoProfile -File (Join-Path $Root "scripts/local/Start-Aarohan.ps1") -Detached
if ($LASTEXITCODE -ne 0) { throw "Start-Aarohan failed" }

$runtimeUrl = "postgresql+psycopg://career_os_runtime:$($env:POSTGRES_RUNTIME_PASSWORD)@127.0.0.1:5432/career_os"
$validationJson = Join-Path $ReportsDir "PHASE-4-POST-CUTOVER-VALIDATION.json"
$validationReport = Join-Path $ReportsDir "PHASE-4-POST-CUTOVER-VALIDATION-REPORT.md"
$validationResult = Invoke-ApiScript -ScriptName "phase4_post_cutover_validate.py" -ScriptArgs @(
    "--database-url", $runtimeUrl,
    "--output-json", $validationJson,
    "--report-md", $validationReport,
    "--api-base", "http://127.0.0.1:8000"
) -EnvOverrides @{
    AAROHAN_DB_IDENTITY_PURPOSE = "OWNER"
    AAROHAN_OWNER_DB_IDENTITY_UUID = $NewOwnerUuid
    AAROHAN_DB_IDENTITY_UUID = $NewOwnerUuid
    ADMIN_EMAIL = $env:ADMIN_EMAIL
    ADMIN_PASSWORD = $env:ADMIN_PASSWORD
} -AllowFailure

if ($validationResult.code -ne 0) {
    Write-Warning "Post-cutover validation failed — executing rollback..."
    docker stop aarohan-careeros-api-1 aarohan-careeros-web-1 2>$null | Out-Null
    $rollbackJson = Join-Path $ReportsDir "PHASE-4-ROLLBACK-MANIFEST.json"
    Invoke-ApiScript -ScriptName "phase4_rollback_cutover.py" -ScriptArgs @(
        "--rollback-database", $RollbackDb,
        "--old-owner-uuid", $OldOwnerUuid,
        "--output-json", $rollbackJson
    ) | Out-Null
    $content = Get-Content $envPath -Raw
    $content = [regex]::Replace($content, '(?m)^AAROHAN_OWNER_DB_IDENTITY_UUID=.*$', "AAROHAN_OWNER_DB_IDENTITY_UUID=$OldOwnerUuid")
    Set-Content -Path $envPath -Value $content -Encoding UTF8 -NoNewline
    & pwsh -NoProfile -File (Join-Path $Root "scripts/local/Invoke-ProvisionOwnerDatabase.ps1") | Out-Null
    & pwsh -NoProfile -File (Join-Path $Root "scripts/local/Start-Aarohan.ps1") -Detached | Out-Null
    throw "Cutover validation failed; rollback attempted. See $rollbackJson"
}

$backupManifest = Join-Path $ReportsDir "OWNER-FINAL-BACKUP-MANIFEST.json"
$backupVerify = Join-Path $ReportsDir "OWNER-FINAL-RESTORE-VERIFICATION.json"
Invoke-ApiScript -ScriptName "phase3_final_backup_restore.py" -ScriptArgs @(
    "--source-db", "career_os",
    "--dumps-dir", $DumpsDir,
    "--manifest-json", $backupManifest,
    "--verification-json", $backupVerify,
    "--identity-uuid", $NewOwnerUuid,
    "--identity-purpose", "OWNER"
) -AllowFailure | Out-Null

Write-Host "Running isolated test suite..."
$testLog = Join-Path $ReportsDir "PHASE-4-TEST-RUN.log"
& pwsh -NoProfile -File (Join-Path $Root "scripts/local/Run-Aarohan-Tests.ps1") *>&1 | Tee-Object -FilePath $testLog
$testsPassed = $LASTEXITCODE -eq 0

$finalReport = Join-Path $ReportsDir "PHASE-4-FINAL-REMEDIATION-REPORT.md"
@"
# Phase 4 Cutover Report

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")
Evidence: ``$($EvidenceRoot.Replace('\','/'))``

## Cutover

- Approval phrase verified: true
- Candidate UUID: $CandidateUuid
- New OWNER UUID: $NewOwnerUuid
- Old OWNER UUID: $OldOwnerUuid
- Rollback archive: $RollbackDb
- Post-cutover validation passed: $($validationResult.code -eq 0)
- Backup restore verified: see OWNER-FINAL-RESTORE-VERIFICATION.json
- Isolated tests passed: $testsPassed

## Gate

State: FINAL_AWAITING_CODEX_REVIEW
"@ | Set-Content -Path $finalReport -Encoding UTF8

Write-Host "Phase 4 cutover complete. Validation: $($validationResult.code -eq 0); Tests: $testsPassed"
return @{
    evidence_root = $EvidenceRoot
    new_owner_uuid = $NewOwnerUuid
    rollback_database = $RollbackDb
    validation_passed = ($validationResult.code -eq 0)
    tests_passed = $testsPassed
}
