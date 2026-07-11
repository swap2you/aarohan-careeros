#Requires -Version 5.1
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root
. (Join-Path $Root "scripts/local/Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root
$env:AAROHAN_DB_IDENTITY_PURPOSE = "OWNER"
$env:AAROHAN_OWNER_DB_IDENTITY_UUID = "8651fd13-3f74-479e-b20f-e433b5d6b87c"
$env:AAROHAN_DB_IDENTITY_UUID = "8651fd13-3f74-479e-b20f-e433b5d6b87c"
$runtimeUrl = "postgresql+psycopg://career_os_runtime:$($env:POSTGRES_RUNTIME_PASSWORD)@127.0.0.1:5432/career_os"
$reports = Join-Path $Root "artifacts\recovery\incident-20260709\phase4-resume-20260711_043000\reports"
New-Item -ItemType Directory -Force -Path $reports | Out-Null
Push-Location (Join-Path $Root "apps\api")
$env:PYTHONPATH = "."
.\.venv\Scripts\python scripts/phase4_validate_oauth.py --database-url $runtimeUrl --output-json (Join-Path $reports "PHASE-4-OAUTH-VALIDATION.json")
$oauthCode = $LASTEXITCODE
.\.venv\Scripts\python scripts/phase4_post_cutover_validate.py --database-url $runtimeUrl --output-json (Join-Path $reports "PHASE-4-POST-CUTOVER-VALIDATION.json") --report-md (Join-Path $reports "PHASE-4-POST-CUTOVER-VALIDATION-REPORT.md") --api-base "http://127.0.0.1:8000"
$valCode = $LASTEXITCODE
Pop-Location
Write-Host "OAuth: $oauthCode Validation: $valCode"
exit [Math]::Max($oauthCode, $valCode)
