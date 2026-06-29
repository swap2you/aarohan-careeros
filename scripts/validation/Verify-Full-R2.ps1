#Requires -Version 5.1
<#
.SYNOPSIS
  Canonical non-destructive R2 full validation entry point.
.DESCRIPTION
  Coordinates repository checks, scans, backend/frontend tests, Docker health,
  and optional live checks. Never deletes data or volumes. Returns non-zero on failure.
#>
param(
    [switch]$SkipDocker,
    [switch]$SkipPlaywright,
    [switch]$LiveOAuth,
    [switch]$LiveGmail
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportDir = Join-Path $Root "generated/validation-reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$reportPath = Join-Path $reportDir "verify-full-r2-$timestamp.txt"

$results = [ordered]@{}
$failed = $false

function Log([string]$Message) {
    Write-Host $Message
    Add-Content -Path $reportPath -Value $Message
}

function Step {
    param([string]$Name, [scriptblock]$Action)
    Log "`n>> $Name"
    try {
        & $Action
        if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "exit $LASTEXITCODE" }
        $script:results[$Name] = "PASS"
        Log "[PASS] $Name"
    } catch {
        $script:results[$Name] = "FAIL: $_"
        $script:failed = $true
        Log "[FAIL] $Name - $_"
    }
}

Log "=== Aarohan Verify-Full-R2 ==="
Log "Timestamp: $timestamp"
Log "Branch: $(git branch --show-current)"
Log "HEAD: $(git rev-parse HEAD)"

Step "git_clean" {
    $status = git status --porcelain
    if ($status) { throw "working tree not clean`n$status" }
}

Step "tag_audit" {
    $required = @("r2.6.1", "r2.7.0")
    foreach ($t in $required) {
        if (-not (git rev-parse "refs/tags/$t" 2>$null)) { throw "missing tag $t" }
    }
    Log "Immutable tags present (no force-update performed by this script)"
}

Step "secret_scan" { python scripts/validation/secret_scan.py }
Step "prohibited_source_scan" { python scripts/validation/prohibited_source_scan.py }

Push-Location apps/api
if (-not (Test-Path .venv)) {
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt -q
}
Step "pytest" { .\.venv\Scripts\pytest -q --tb=no 2>&1 | Tee-Object -FilePath $reportPath -Append | Out-Null }
Pop-Location

Push-Location apps/web
if (-not (Test-Path node_modules)) { npm ci --silent }
Step "web_lint_type_build" {
    npm run build 2>&1 | Tee-Object -FilePath $reportPath -Append | Out-Null
}
if (-not $SkipPlaywright) {
    Step "playwright" { npm run test:e2e 2>&1 | Tee-Object -FilePath $reportPath -Append | Out-Null }
}
Pop-Location

if (-not $SkipDocker) {
    Step "docker_health" {
        docker compose ps 2>&1 | Out-String | ForEach-Object { Log $_ }
        $h = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 15
        if ($h.status -ne "ok") { throw "API unhealthy" }
    }
}

if ($LiveOAuth) {
    Step "live_oauth_optional" {
        Log "Owner must confirm Drive root in Settings — not automated"
    }
}

if ($LiveGmail) {
    Step "live_gmail_optional" {
        Log "Run Gmail sync with live OAuth when owner authorized — optional"
    }
}

Log "`n=== Summary ==="
$results.GetEnumerator() | ForEach-Object { Log "$($_.Key): $($_.Value)" }
Log "Report: $reportPath"

if ($failed) {
    Log "`nVERIFY-FULL-R2: FAIL"
    exit 1
}
Log "`nVERIFY-FULL-R2: PASS"
exit 0
