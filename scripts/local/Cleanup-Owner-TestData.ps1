#Requires -Version 5.1
<#
.SYNOPSIS
  Dry-run (default) or execute cleanup of fixture/test data from owner database.
.DESCRIPTION
  Uses data_provenance only — never deletes by company name substring alone.
#>
param(
    [switch]$Execute,
    [switch]$SkipBackup
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

$reportDir = Join-Path $Root "generated/cleanup-reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $reportDir "owner-cleanup-dryrun-$stamp.txt"

function Log([string]$Message) {
    Write-Host $Message
    Add-Content -Path $reportPath -Value $Message
}

Log "=== Owner test/fixture cleanup report ==="
Log "Mode: $(if ($Execute) { 'EXECUTE' } else { 'DRY-RUN' })"
Log "Timestamp: $stamp"

$countsBefore = docker compose exec -T postgres psql -U career_os -d career_os -t -A -c @"
SELECT 'jobs_fixture', count(*) FROM jobs WHERE data_provenance IN ('fixture','test');
SELECT 'companies_fixture', count(*) FROM companies WHERE data_provenance IN ('fixture','test');
SELECT 'applications_fixture', count(*) FROM applications WHERE data_provenance IN ('fixture','test');
SELECT 'jobs_live', count(*) FROM jobs WHERE data_provenance NOT IN ('fixture','test');
"@ 2>&1
Log "Before counts:"
$countsBefore | ForEach-Object { Log $_ }

$sql = @"
-- Proposed deletions (provenance-based only)
SELECT 'application' AS kind, id, job_id FROM applications WHERE data_provenance IN ('fixture','test');
SELECT 'job' AS kind, id, company FROM jobs WHERE data_provenance IN ('fixture','test');
SELECT 'company' AS kind, id, canonical_name FROM companies WHERE data_provenance IN ('fixture','test')
  AND id NOT IN (SELECT DISTINCT company_id FROM jobs WHERE company_id IS NOT NULL AND data_provenance NOT IN ('fixture','test'));
"@

Log "`nProposed deletions:"
$proposed = docker compose exec -T postgres psql -U career_os -d career_os -c $sql 2>&1
Log ($proposed | Out-String)

if (-not $Execute) {
    Log "`nDRY-RUN complete. Re-run with -Execute after owner review."
    Log "Report: $reportPath"
    exit 0
}

$confirm = Read-Host "Type DELETE-FIXTURE-DATA to proceed"
if ($confirm -ne "DELETE-FIXTURE-DATA") {
    throw "Cleanup cancelled."
}

if (-not $SkipBackup) {
    $backupDir = Join-Path $Root "artifacts/backups"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $backupFile = Join-Path $backupDir "pre_cleanup_$stamp.sql"
    docker compose exec -T postgres pg_dump -U career_os career_os | Set-Content -Path $backupFile -Encoding utf8
    Log "Backup written: $backupFile"
}

$deleteSql = @"
BEGIN;
DELETE FROM applications WHERE data_provenance IN ('fixture','test');
DELETE FROM jobs WHERE data_provenance IN ('fixture','test');
DELETE FROM companies WHERE data_provenance IN ('fixture','test')
  AND id NOT IN (SELECT DISTINCT company_id FROM jobs WHERE company_id IS NOT NULL);
COMMIT;
"@
docker compose exec -T postgres psql -U career_os -d career_os -c $deleteSql | Out-Null
Log "Cleanup executed."
Log "Report: $reportPath"
