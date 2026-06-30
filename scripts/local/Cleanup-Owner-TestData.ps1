#Requires -Version 5.1
<#
.SYNOPSIS
  Dry-run (default) or execute cleanup of fixture/test data from owner database.
.DESCRIPTION
  Uses data_provenance and legacy inventory classification — never deletes by name substring alone.
#>
param(
    [switch]$Execute,
    [switch]$SkipBackup,
    [switch]$BackfillProvenance
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

$backfillArg = if ($BackfillProvenance) { "--backfill" } else { "" }
Log "`nRunning legacy inventory (provenance-based classification)..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$backfillFlag = if ($BackfillProvenance) { "--backfill" } else { "" }
$inventoryOut = docker compose exec -T api python scripts/inventory_legacy_data.py --stdout $backfillFlag 2>&1 | Out-String
$ErrorActionPreference = $prevEap
$inventoryOut -split "`n" | ForEach-Object { if ($_.Trim()) { Log $_ } }

$countsBefore = docker compose exec -T postgres psql -U career_os -d career_os -t -A -c @"
SELECT 'jobs_fixture', count(*) FROM jobs WHERE data_provenance IN ('fixture','test');
SELECT 'jobs_test', count(*) FROM jobs WHERE data_provenance = 'test';
SELECT 'companies_fixture', count(*) FROM companies WHERE data_provenance IN ('fixture','test');
SELECT 'applications_fixture', count(*) FROM applications WHERE data_provenance IN ('fixture','test');
SELECT 'jobs_live', count(*) FROM jobs WHERE data_provenance NOT IN ('fixture','test');
SELECT 'companies_live', count(*) FROM companies WHERE data_provenance NOT IN ('fixture','test');
SELECT 'applications_live', count(*) FROM applications WHERE data_provenance NOT IN ('fixture','test');
SELECT 'document_versions_fixture', count(*) FROM application_document_versions v
  JOIN applications a ON a.id = v.application_id WHERE a.data_provenance IN ('fixture','test');
SELECT 'audit_e2e_actor', count(*) FROM audit_logs WHERE actor = 'e2e@test.local';
SELECT 'gmail_reviews_quarantined', count(*) FROM gmail_ingest_reviews WHERE status = 'quarantined';
"@ 2>&1
Log "`nAfter-inventory counts:"
$countsBefore | ForEach-Object { Log $_ }

$sql = @"
SELECT 'application' AS kind, a.id, a.job_id, j.company, j.title
FROM applications a JOIN jobs j ON j.id = a.job_id
WHERE a.data_provenance IN ('fixture','test') OR j.data_provenance IN ('fixture','test');
SELECT 'job' AS kind, id, company, title, data_provenance, source, external_id
FROM jobs WHERE data_provenance IN ('fixture','test');
SELECT 'company' AS kind, id, canonical_name, data_provenance
FROM companies WHERE data_provenance IN ('fixture','test')
  AND id NOT IN (
    SELECT DISTINCT company_id FROM jobs
    WHERE company_id IS NOT NULL AND data_provenance NOT IN ('fixture','test')
  );
"@

Log "`nProposed deletions (provenance-based only):"
$proposed = docker compose exec -T postgres psql -U career_os -d career_os -c $sql 2>&1
Log ($proposed | Out-String)

if (-not $Execute) {
    Log "`nDRY-RUN complete. Review inventory report above."
    Log "Optional: re-run with -BackfillProvenance to tag records before delete review."
    Log "Re-run with -Execute after owner approval."
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
DELETE FROM application_timeline_events WHERE application_id IN (
  SELECT id FROM applications WHERE data_provenance IN ('fixture','test')
     OR job_id IN (SELECT id FROM jobs WHERE data_provenance IN ('fixture','test'))
);
DELETE FROM application_document_versions WHERE application_id IN (
  SELECT id FROM applications WHERE data_provenance IN ('fixture','test')
     OR job_id IN (SELECT id FROM jobs WHERE data_provenance IN ('fixture','test'))
);
DELETE FROM approval_actions WHERE application_id IN (
  SELECT id FROM applications WHERE data_provenance IN ('fixture','test')
);
DELETE FROM applications WHERE data_provenance IN ('fixture','test')
   OR job_id IN (SELECT id FROM jobs WHERE data_provenance IN ('fixture','test'));
DELETE FROM job_scores WHERE job_id IN (SELECT id FROM jobs WHERE data_provenance IN ('fixture','test'));
DELETE FROM jobs WHERE data_provenance IN ('fixture','test');
DELETE FROM companies WHERE data_provenance IN ('fixture','test')
  AND id NOT IN (SELECT DISTINCT company_id FROM jobs WHERE company_id IS NOT NULL);
COMMIT;
"@
docker compose exec -T postgres psql -U career_os -d career_os -c $deleteSql | Out-Null
Log "Cleanup executed."
Log "Report: $reportPath"
