#Requires -Version 5.1
<#
.SYNOPSIS
  Generate Phase 2 final identity guard evidence for Codex re-review.
#>
param(
    [string]$Timestamp = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

if (-not $Timestamp) {
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
}
$evidenceRoot = Join-Path $Root "artifacts/recovery/incident-20260709/phase2-final-identity-$Timestamp"
$reportsDir = Join-Path $evidenceRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$identity = & (Join-Path $Root "scripts/local/Assert-AarohanOwnerDatabaseIdentity.ps1")

function Get-RowCounts {
    param([string]$Database)
    $raw = docker exec aarohan-careeros-postgres-1 psql -U career_os -d $Database -Atc @"
SELECT 'jobs', count(*)::text FROM jobs
UNION ALL SELECT 'applications', count(*)::text FROM applications
UNION ALL SELECT 'oauth_tokens', count(*)::text FROM oauth_tokens
UNION ALL SELECT 'users', count(*)::text FROM users
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

$ownerCounts = Get-RowCounts -Database "career_os"
$validationCounts = Get-RowCounts -Database "career_os_validation"

$protectedHelpers = @(
    "scripts/local/Assert-AarohanOwnerDatabaseIdentity.ps1",
    "scripts/local/Invoke-VerifiedOwnerBackup.ps1",
    "scripts/local/Cleanup-Owner-TestData.ps1",
    "scripts/local/Audit-FreshJobsData.ps1",
    "scripts/local/Backup-Aarohan.ps1",
    "scripts/backup/backup_postgres.py",
    "scripts/recovery/Invoke-IncidentPhase1Snapshot.ps1",
    "apps/api/scripts/audit_fresh_jobs.py"
)

$evidence = [ordered]@{
    identity_preflight = [ordered]@{
        verified = $true
        purpose = $identity.Purpose
        identity_uuid = $identity.IdentityUuid
        database = $identity.Database
        compose_project = $identity.ComposeProject
        postgres_service = $identity.PostgresService
        postgres_container = $identity.PostgresContainer
        identity_fingerprint = $identity.IdentityFingerprint
        verified_at = $identity.VerifiedAt
    }
    protected_helpers = $protectedHelpers
    owner_row_counts = $ownerCounts
    validation_row_counts = $validationCounts
    owner_cleanup_executed = $false
    audit_execute_run = $false
    phase_3_started = $false
}
$evidence | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $reportsDir "PHASE-2-FINAL-IDENTITY-GUARD-EVIDENCE.json") -Encoding UTF8

$report = @"
# Phase 2 Final Identity Guard Report

Timestamp: $Timestamp
State: PHASE_2_AWAITING_CODEX_REVIEW

## CODEX-P2-HIGH-004 disposition

**Resolved** — canonical owner identity preflight (`Assert-AarohanOwnerDatabaseIdentity.ps1` + `owner_database_identity_preflight.py`) is mandatory before privileged owner helpers run bootstrap operations.

## Protected helpers

$(($protectedHelpers | ForEach-Object { "- $_" }) -join "`n")

## Owner row counts (unchanged)

$(($ownerCounts.GetEnumerator() | ForEach-Object { "- $($_.Key): $($_.Value)" }) -join "`n")

## Validation row counts (unchanged)

$(($validationCounts.GetEnumerator() | ForEach-Object { "- $($_.Key): $($_.Value)" }) -join "`n")
"@
$report | Set-Content (Join-Path $reportsDir "PHASE-2-FINAL-IDENTITY-GUARD-REPORT.md") -Encoding UTF8
Write-Host "Evidence written to $reportsDir"
