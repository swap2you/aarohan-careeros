#Requires -Version 5.1
<#
.SYNOPSIS
  Dry-run (default) or execute cleanup of fixture/test data from owner database.
#>
param(
    [switch]$Execute,
    [switch]$SkipBackup,
    [switch]$BackfillProvenance
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

if ($Execute -and $SkipBackup) {
    throw "Execute mode never accepts -SkipBackup. A same-run verified backup is mandatory."
}

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
. (Join-Path $PSScriptRoot "Assert-AarohanOwnerDatabaseIdentity.ps1")

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

$identity = Assert-AarohanOwnerDatabaseIdentity
Log "Owner identity preflight verified: purpose=$($identity.Purpose) database=$($identity.Database) fingerprint=$($identity.IdentityFingerprint)"

Import-AarohanRepoEnvLocal -Root $Root
$envFile = Join-Path $Root ".env.local"

Log "`nRunning legacy inventory (provenance-based classification)..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$backfillFlag = if ($BackfillProvenance) { "--backfill" } else { "" }
$inventoryOut = docker compose --env-file $envFile exec -T api python scripts/inventory_legacy_data.py --stdout $backfillFlag 2>&1 | Out-String
$ErrorActionPreference = $prevEap
$inventoryOut -split "`n" | ForEach-Object { if ($_.Trim()) { Log $_ } }

$countsBefore = docker compose --env-file $envFile exec -T postgres psql -U career_os -d career_os -t -A -c @"
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
$proposed = docker compose --env-file $envFile exec -T postgres psql -U career_os -d career_os -c $sql 2>&1
Log ($proposed | Out-String)

if (-not $Execute) {
    Log "`nDRY-RUN complete. Review inventory report above."
    Log "Optional: re-run with -BackfillProvenance to tag records before delete review."
    Log "Re-run with -Execute after owner approval."
    Log "Report: $reportPath"
    exit 0
}

$sameRunStartedAt = (Get-Date).ToUniversalTime().ToString('o')

$confirm = Read-Host "Type DELETE-FIXTURE-DATA to proceed"
if ($confirm -ne "DELETE-FIXTURE-DATA") {
    throw "Cleanup cancelled."
}

$backup = & pwsh -NoProfile -File (Join-Path $PSScriptRoot "Invoke-VerifiedOwnerBackup.ps1")
if (-not $backup.Verified) {
    throw "Verified backup gate failed before execute."
}

Push-Location (Join-Path $Root "apps/api")
$env:PYTHONPATH = "."
$identityPayload = [ordered]@{
    verified = $true
    purpose = $identity.Purpose
    identity_uuid = $identity.IdentityUuid
    database = $identity.Database
    compose_project = $identity.ComposeProject
    postgres_service = $identity.PostgresService
    postgres_container = $identity.PostgresContainer
    host = $identity.Host
    port = $identity.Port
    privileged_user = $identity.PrivilegedUser
    identity_fingerprint = $identity.IdentityFingerprint
    verified_at = $identity.VerifiedAt
}
$identityJson = ($identityPayload | ConvertTo-Json -Compress)
$manifestCheck = .\.venv\Scripts\python scripts/assert_same_run_backup_manifest.py `
    --manifest-path $backup.ManifestPath `
    --dump-path $backup.DumpPath `
    --same-run-started-at $sameRunStartedAt `
    --identity-json $identityJson 2>&1 | Out-String
Pop-Location
if ($LASTEXITCODE -ne 0) {
    throw "Same-run backup manifest validation failed before cleanup execute."
}

Log "Verified backup written: $($backup.DumpPath) ($($backup.SizeBytes) bytes)"
Log "Verified backup SHA-256: $($backup.Sha256)"
Log "Verified backup manifest: $($backup.ManifestPath)"
Log "Backup identity fingerprint: $($identity.IdentityFingerprint)"

if ([string]::IsNullOrWhiteSpace($env:AAROHAN_DESTRUCTIVE_TOKEN)) {
    throw "AAROHAN_DESTRUCTIVE_TOKEN must be set in .env.local for destructive owner operations."
}
$tokenConfirm = Read-Host "Enter AAROHAN_DESTRUCTIVE_TOKEN to confirm destructive cleanup"
if ($tokenConfirm -ne $env:AAROHAN_DESTRUCTIVE_TOKEN) {
    throw "Destructive token mismatch; cleanup cancelled."
}

$expectedUuid = $identity.IdentityUuid.Replace("'", "''")
$deleteSql = @"
BEGIN;
DO `$`$
DECLARE
  marker_count integer;
  marker_purpose text;
  marker_uuid text;
BEGIN
  SELECT count(*) INTO marker_count FROM aarohan_meta.database_identity;
  IF marker_count <> 1 THEN
    RAISE EXCEPTION 'owner identity marker count %', marker_count;
  END IF;
  SELECT purpose, identity_uuid INTO marker_purpose, marker_uuid
  FROM aarohan_meta.database_identity ORDER BY id LIMIT 1;
  IF upper(marker_purpose) <> 'OWNER' THEN
    RAISE EXCEPTION 'owner identity purpose mismatch';
  END IF;
  IF lower(marker_uuid) <> lower('$expectedUuid') THEN
    RAISE EXCEPTION 'owner identity uuid mismatch';
  END IF;
  IF current_database() <> 'career_os' THEN
    RAISE EXCEPTION 'owner identity database mismatch';
  END IF;
END `$`$;
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

docker compose --env-file $envFile exec -T postgres psql -U career_os -d career_os -c $deleteSql | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Cleanup execute failed; transaction rolled back."
}

$countsAfter = docker compose --env-file $envFile exec -T postgres psql -U career_os -d career_os -t -A -c @"
SELECT 'jobs_live', count(*) FROM jobs WHERE data_provenance NOT IN ('fixture','test');
SELECT 'applications_live', count(*) FROM applications WHERE data_provenance NOT IN ('fixture','test');
"@ 2>&1
Log "Cleanup executed."
Log "After counts:"
$countsAfter | ForEach-Object { Log $_ }

$executionManifest = [ordered]@{
    executed_at = (Get-Date).ToUniversalTime().ToString('o')
    identity_fingerprint = $identity.IdentityFingerprint
    identity_uuid = $identity.IdentityUuid
    backup_manifest = $backup.ManifestPath
    backup_sha256 = $backup.Sha256
    same_run_started_at = $sameRunStartedAt
}
$executionManifestPath = Join-Path $reportDir "owner-cleanup-execute-$stamp.json"
$executionManifest | ConvertTo-Json -Depth 4 | Set-Content -Path $executionManifestPath -Encoding UTF8
Log "Execution manifest: $executionManifestPath"
Log "Report: $reportPath"
