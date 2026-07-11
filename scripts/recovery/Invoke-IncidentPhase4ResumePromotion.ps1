#Requires -Version 5.1
<#
.SYNOPSIS
  Resume Phase 4 cutover from preserved failed-promotion database after rollback.
#>
param(
    [string]$FailedPromotionDb = "career_os_failed_promotion_20260711_042447",
    [string]$NewOwnerUuid = "8651fd13-3f74-479e-b20f-e433b5d6b87c",
    [string]$OldOwnerUuid = "2bfda5fc-3a2b-4dd4-a7a9-65e8432f7c03",
    [string]$Timestamp = "",
    [string]$ContainerName = "aarohan-careeros-postgres-1",
    [string]$PgUser = "career_os"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $Root "scripts/local/Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

if (-not $Timestamp) { $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss" }
$EvidenceRoot = Join-Path $Root "artifacts\recovery\incident-20260709\phase4-resume-$Timestamp"
$ReportsDir = Join-Path $EvidenceRoot "reports"
$DumpsDir = Join-Path $EvidenceRoot "dumps"
New-Item -ItemType Directory -Force -Path $ReportsDir, $DumpsDir | Out-Null

docker stop aarohan-careeros-api-1 aarohan-careeros-web-1 2>$null | Out-Null
Start-Sleep -Seconds 2

$rollbackArchive = "career_os_rollback_resume_$Timestamp"
docker exec $ContainerName psql -U $PgUser -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('career_os','$FailedPromotionDb') AND pid <> pg_backend_pid();" | Out-Null
docker exec $ContainerName psql -U $PgUser -d postgres -c "ALTER DATABASE career_os RENAME TO `"$rollbackArchive`";" | Out-Null
docker exec $ContainerName psql -U $PgUser -d postgres -c "ALTER DATABASE `"$FailedPromotionDb`" RENAME TO career_os;" | Out-Null

$envPath = Join-Path $Root ".env.local"
$content = Get-Content $envPath -Raw
$content = [regex]::Replace($content, '(?m)^AAROHAN_OWNER_DB_IDENTITY_UUID=.*$', "AAROHAN_OWNER_DB_IDENTITY_UUID=$NewOwnerUuid")
Set-Content -Path $envPath -Value $content -Encoding UTF8 -NoNewline
Import-AarohanRepoEnvLocal -Root $Root

& pwsh -NoProfile -File (Join-Path $Root "scripts/local/Invoke-ProvisionOwnerDatabase.ps1")
& pwsh -NoProfile -File (Join-Path $Root "scripts/local/Start-Aarohan.ps1") -Detached

$ApiDir = Join-Path $Root "apps\api"
$runtimeUrl = "postgresql+psycopg://career_os_runtime:$($env:POSTGRES_RUNTIME_PASSWORD)@127.0.0.1:5432/career_os"
Push-Location $ApiDir
$env:PYTHONPATH = "."
$env:AAROHAN_DB_IDENTITY_PURPOSE = "OWNER"
$env:AAROHAN_OWNER_DB_IDENTITY_UUID = $NewOwnerUuid
$env:AAROHAN_DB_IDENTITY_UUID = $NewOwnerUuid
.\.venv\Scripts\python scripts/phase4_post_cutover_validate.py `
    --database-url $runtimeUrl `
    --output-json (Join-Path $ReportsDir "PHASE-4-POST-CUTOVER-VALIDATION.json") `
    --report-md (Join-Path $ReportsDir "PHASE-4-POST-CUTOVER-VALIDATION-REPORT.md") `
    --api-base "http://127.0.0.1:8000"
$validationCode = $LASTEXITCODE
Pop-Location

if ($validationCode -ne 0) { throw "Post-cutover validation failed after resume" }

Push-Location $ApiDir
$env:PYTHONPATH = "."
.\.venv\Scripts\python scripts/phase3_final_backup_restore.py `
    --source-db career_os `
    --dumps-dir $DumpsDir `
    --manifest-json (Join-Path $ReportsDir "OWNER-FINAL-BACKUP-MANIFEST.json") `
    --verification-json (Join-Path $ReportsDir "OWNER-FINAL-RESTORE-VERIFICATION.json") `
    --identity-uuid $NewOwnerUuid `
    --identity-purpose OWNER
Pop-Location

$testLog = Join-Path $ReportsDir "PHASE-4-TEST-RUN.log"
& pwsh -NoProfile -File (Join-Path $Root "scripts/local/Run-Aarohan-Tests.ps1") *>&1 | Tee-Object -FilePath $testLog

Write-Host "Resume promotion complete. Validation exit: $validationCode Tests exit: $LASTEXITCODE"
