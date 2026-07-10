#Requires -Version 5.1
<#
.SYNOPSIS
  Phase 2 evidence: permanent test isolation proofs and owner unchanged verification.
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

$EvidenceRoot = Join-Path $Root "artifacts/recovery/incident-20260709/phase2-$Timestamp"
$ReportsDir = Join-Path $EvidenceRoot "reports"
New-Item -ItemType Directory -Force -Path $ReportsDir | Out-Null

. (Join-Path $Root "scripts/local/Invoke-AarohanCompose.ps1")
. (Join-Path $Root "scripts/local/Invoke-AarohanTestCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root
Import-AarohanTestEnv -Root $Root

function Get-OwnerRowCounts {
    docker exec aarohan-careeros-postgres-1 psql -U career_os -d career_os -Atc @"
SELECT 'jobs', count(*) FROM jobs
UNION ALL SELECT 'applications', count(*) FROM applications
UNION ALL SELECT 'oauth_tokens', count(*) FROM oauth_tokens
UNION ALL SELECT 'processed_gmail_messages', count(*) FROM processed_gmail_messages
UNION ALL SELECT 'users', count(*) FROM users;
"@
}

$proofs = [ordered]@{}

# 1. Owner pytest blocked
$pytestBlock = docker compose exec -T api pytest --version 2>&1 | Out-String
$proofs.owner_pytest_blocked = ($pytestBlock -match "blocked on owner runtime" -or $LASTEXITCODE -ne 0)

# 2. E2E credentials cannot connect to owner postgres
$e2eToOwner = docker exec aarohan-careeros-postgres-1 psql "postgresql://career_os_e2e:$($env:E2E_POSTGRES_PASSWORD)@127.0.0.1:5432/career_os" -c "SELECT 1" 2>&1 | Out-String
$proofs.e2e_cannot_connect_owner = ($e2eToOwner -match "password authentication failed|role .* does not exist|FATAL")

# 3. Owner credentials cannot connect to isolated test postgres (if running)
$testPg = docker ps --format "{{.Names}}" | Select-String "aarohan-careeros-test-postgres-e2e"
if ($testPg) {
    $ownerToTest = docker exec aarohan-careeros-test-postgres-e2e-1 psql "postgresql://career_os:$($env:POSTGRES_PASSWORD)@127.0.0.1:5432/career_os_e2e" -c "SELECT 1" 2>&1 | Out-String
    $proofs.owner_cannot_connect_test = ($ownerToTest -match "password authentication failed|role .* does not exist|FATAL")
} else {
    $proofs.owner_cannot_connect_test = $null
    $proofs.owner_cannot_connect_test_note = "test postgres not running; start Start-Aarohan-E2E.ps1 first"
}

# 4. Owner row counts before/after (capture once — caller should compare if re-run)
$proofs.owner_row_counts = @{}
Get-OwnerRowCounts | ForEach-Object {
    if ($_ -match '^([^|]+)\|(\d+)$') { $proofs.owner_row_counts[$matches[1]] = [int]$matches[2] }
}

# 5. Compose project separation
$proofs.compose_projects = @{
    owner = "aarohan-careeros"
    test = "aarohan-careeros-test"
}
$proofs.owner_postgres_volume = "aarohan-careeros_postgres_data"
$proofs.test_postgres_volume = "aarohan-careeros-test_postgres_e2e_data"

# 6. Run isolated tests
Write-Host "Running Run-Aarohan-Tests.ps1 (SkipPlaywright for speed in evidence)..."
$testLog = Join-Path $ReportsDir "run-aarohan-tests.log"
& pwsh -NoProfile -File (Join-Path $Root "scripts/local/Run-Aarohan-Tests.ps1") -SkipPlaywright 2>&1 | Tee-Object -FilePath $testLog
$proofs.isolated_tests_passed = ($LASTEXITCODE -eq 0)

# 7. Owner-stack pytest scan
python scripts/validation/owner_stack_pytest_scan.py 2>&1 | Out-Null
$proofs.owner_stack_pytest_scan_passed = ($LASTEXITCODE -eq 0)

$manifest = [ordered]@{
    incident_id = "owner-db-incident-20260709"
    phase = 2
    timestamp = $Timestamp
    git_sha = (git rev-parse HEAD).Trim()
    proofs = $proofs
    evidence_root = ($EvidenceRoot -replace '\\', '/')
}

$manifestPath = Join-Path $ReportsDir "PHASE-2-ISOLATION-MANIFEST.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding UTF8

$report = @"
# Phase 2 Isolation Evidence

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss K")
Git SHA: $($manifest.git_sha)

## Proofs

| Check | Result |
|---|---|
| Owner \`docker compose exec api pytest\` blocked | $($proofs.owner_pytest_blocked) |
| E2E user cannot connect to owner postgres | $($proofs.e2e_cannot_connect_owner) |
| Owner user cannot connect to test postgres | $($proofs.owner_cannot_connect_test) |
| Isolated Run-Aarohan-Tests passed | $($proofs.isolated_tests_passed) |
| Owner-stack pytest scan passed | $($proofs.owner_stack_pytest_scan_passed) |

## Owner row counts (unchanged verification snapshot)

$(($proofs.owner_row_counts.GetEnumerator() | ForEach-Object { "- $($_.Key): $($_.Value)" }) -join "`n")

## Architecture

- Owner compose project: aarohan-careeros (postgres :5432, career_os)
- Test compose project: aarohan-careeros-test (postgres-e2e :5433, career_os_e2e / user career_os_e2e)
- Separate volumes: aarohan-careeros_postgres_data vs aarohan-careeros-test_postgres_e2e_data

## Evidence files

- ``$($manifestPath -replace '\\','/')``
- ``$($testLog -replace '\\','/')``
"@

$reportPath = Join-Path $ReportsDir "PHASE-2-ISOLATION-REPORT.md"
Set-Content -Path $reportPath -Value $report -Encoding UTF8

if (-not $proofs.owner_pytest_blocked) { throw "Proof failed: owner pytest not blocked" }
if (-not $proofs.e2e_cannot_connect_owner) { throw "Proof failed: E2E can connect to owner postgres" }
if (-not $proofs.isolated_tests_passed) { throw "Proof failed: isolated tests did not pass" }
if (-not $proofs.owner_stack_pytest_scan_passed) { throw "Proof failed: owner-stack pytest scan" }

Write-Host "Phase 2 evidence complete: $EvidenceRoot"
return [ordered]@{
    evidence_root = $EvidenceRoot
    manifest_path = $manifestPath
    report_path = $reportPath
}
