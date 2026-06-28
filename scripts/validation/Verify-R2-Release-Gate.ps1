#Requires -Version 5.1
<#
.SYNOPSIS
  Canonical R2 release gate verification (local).
#>
param(
    [switch]$SkipDocker,
    [switch]$SkipPlaywright
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

$results = [ordered]@{}
$failed = $false

function Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "`n>> $Name"
    try {
        & $Action
        if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "exit $LASTEXITCODE" }
        $script:results[$Name] = "PASS"
        Write-Host "[PASS] $Name"
    } catch {
        $script:results[$Name] = "FAIL: $_"
        $script:failed = $true
        Write-Host "[FAIL] $Name - $_"
    }
}

Write-Host "=== Aarohan R2 Release Gate ==="
Write-Host "Branch: $(git branch --show-current)"
Write-Host "HEAD: $(git rev-parse --short HEAD)"

Step "secret_scan" { python scripts/validation/secret_scan.py }
Step "prohibited_source_scan" { python scripts/validation/prohibited_source_scan.py }

Push-Location apps/api
if (-not (Test-Path .venv)) {
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt -q
}
Step "pytest" { .\.venv\Scripts\pytest -q }
Pop-Location

Push-Location apps/web
if (-not (Test-Path node_modules)) { npm ci --silent }
Step "web_build" { npm run build }
if (-not $SkipPlaywright) {
    Step "playwright" { npm run test:e2e }
}
Pop-Location

if (-not $SkipDocker) {
    Step "docker_compose_ps" {
        docker compose ps 2>$null | Out-String | Write-Host
    }
    Step "api_health" {
        $h = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
        if ($h.status -ne "ok") { throw "unhealthy" }
    }
}

Write-Host "`n=== Summary ==="
$results.GetEnumerator() | ForEach-Object { Write-Host "$($_.Key): $($_.Value)" }

if ($failed) {
    Write-Host "`nGATE: FAIL"
    exit 1
}
Write-Host "`nGATE: PASS"
exit 0
