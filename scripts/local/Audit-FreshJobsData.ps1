#Requires -Version 5.1
<#
.SYNOPSIS
  Fresh Jobs owner-data audit (Workflow Lock 01). Dry-run by default.

.DESCRIPTION
  Runs analysis inside the Aarohan API container (valid DATABASE_URL / postgres hostname).
  Does not use host Python. Never deletes records. Never prints secrets.

.EXAMPLE
  pwsh .\scripts\local\Audit-FreshJobsData.ps1

.EXAMPLE
  pwsh .\scripts\local\Audit-FreshJobsData.ps1 -Execute -ConfirmationText "ARCHIVE STALE AND INELIGIBLE JOBS"
#>
param(
    [switch]$Execute,
    [string]$ConfirmationText = "",
    [string]$ReportDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $RepoRoot

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")

$ConfirmationPhrase = "ARCHIVE STALE AND INELIGIBLE JOBS"

function Write-AuditFailure {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Test-ApiContainerHealthy {
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5
        return ($h.status -eq "ok")
    } catch {
        return $false
    }
}

function Test-ApiServiceRunning {
    try {
        Import-AarohanRepoEnvLocal -Root $RepoRoot
        $envFile = Join-Path $RepoRoot ".env.local"
        $null = & docker compose --env-file $envFile ps --status running --services 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        $services = & docker compose --env-file $envFile ps --status running --services 2>$null
        return ($services -split "`n" | Where-Object { $_.Trim() -eq "api" }).Count -gt 0
    } catch {
        return $false
    }
}

function Get-RedactedText {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $Text }
    $t = $Text
    $t = [regex]::Replace($t, '(?i)postgresql\+?[^\s]*://[^\s]+', 'postgresql://***')
    $t = [regex]::Replace($t, '(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*\S+', '$1=***')
    $t = [regex]::Replace($t, '(?i)(APP_SECRET|TOKEN_ENCRYPTION_KEY|POSTGRES_PASSWORD)=[^\s]+', '$1=***')
    return $t
}

if (-not $ReportDir) {
    $ReportDir = Join-Path $RepoRoot "generated\job-discovery-audit"
}

Write-Host "Aarohan Fresh Jobs audit" -ForegroundColor Cyan
Write-Host ("Mode: " + $(if ($Execute) { "EXECUTE" } else { "dry-run (default)" }))

Import-AarohanRepoEnvLocal -Root $RepoRoot

if (-not (Test-ApiServiceRunning) -or -not (Test-ApiContainerHealthy)) {
    Write-Host ""
    Write-Host "API container is not running or not healthy." -ForegroundColor Yellow
    Write-Host "Start the stack first:" -ForegroundColor Yellow
    Write-Host "  pwsh .\scripts\local\Start-Aarohan.ps1 -Detached" -ForegroundColor White
    exit 1
}

$hostScript = Join-Path $RepoRoot "apps\api\scripts\audit_fresh_jobs.py"
if (-not (Test-Path $hostScript)) {
    Write-AuditFailure "Audit script missing at $hostScript"
}

$auditArgs = [System.Collections.Generic.List[string]]::new()
if ($Execute) {
    [void]$auditArgs.Add("--execute")
    [void]$auditArgs.Add("--confirmation-text")
    [void]$auditArgs.Add($ConfirmationText)
}

$envFile = Join-Path $RepoRoot ".env.local"
$scriptText = Get-Content -Raw -Path $hostScript

# Pipe host script into container Python so we do not require an image rebuild
# and never depend on host DATABASE_URL / host Python packages.
$pythonOut = $scriptText | & docker compose --env-file $envFile exec -T api python - @($auditArgs.ToArray()) 2>&1 | Out-String
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-AuditFailure ("Audit failed inside API container (exit {0}). {1}" -f $exitCode, (Get-RedactedText $pythonOut).Trim())
}

$jsonText = $null
$start = $pythonOut.IndexOf("{")
$end = $pythonOut.LastIndexOf("}")
if ($start -ge 0 -and $end -gt $start) {
    $jsonText = $pythonOut.Substring($start, $end - $start + 1)
}
if (-not $jsonText) {
    Write-AuditFailure "Audit produced no JSON output. No report written."
}

try {
    $envelope = $jsonText | ConvertFrom-Json
} catch {
    Write-AuditFailure "Audit output was not valid JSON. No report written."
}

if (-not $envelope.ok) {
    Write-AuditFailure (Get-RedactedText ([string]$envelope.error))
}

$report = $envelope.report
$summary = $envelope.summary

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $ReportDir "fresh-jobs-audit-$stamp.json"
($report | ConvertTo-Json -Depth 12) | Set-Content -Path $reportPath -Encoding UTF8

Write-Host ""
Write-Host "=== Fresh Jobs audit summary ===" -ForegroundColor Green
Write-Host ("total_owner_jobs            : {0}" -f $summary.total_owner_jobs)
Write-Host ("proposed_fresh_jobs_count   : {0}" -f $summary.proposed_fresh_jobs_count)
Write-Host ("proposed_archive_count      : {0}" -f $summary.proposed_archive_count)
Write-Host ("proposed_quarantine_count   : {0}" -f $summary.proposed_quarantine_count)
Write-Host ("proposed_reject_count       : {0}" -f $summary.proposed_reject_count)
Write-Host ("report_path                 : {0}" -f $reportPath)
if ($Execute -and $summary.mode -eq "execute") {
    Write-Host ("records_updated             : {0}" -f $summary.records_updated)
} elseif ($Execute -and $summary.execute_error) {
    Write-Host ("execute_error               : {0}" -f $summary.execute_error) -ForegroundColor Yellow
    Write-Host "No records were changed." -ForegroundColor Yellow
}

if (-not $Execute) {
    Write-Host ""
    Write-Host "Dry-run only. To apply archive/reclassify (never deletes):" -ForegroundColor Yellow
    Write-Host ('  pwsh .\scripts\local\Audit-FreshJobsData.ps1 -Execute -ConfirmationText "{0}"' -f $ConfirmationPhrase)
}
