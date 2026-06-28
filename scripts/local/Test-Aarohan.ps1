#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

Write-Host "=== Aarohan Local Validation ==="

function Run-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "`n>> $Name"
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

Run-Step "Secret scan" { python scripts/validation/secret_scan.py }
Run-Step "Prohibited source scan" { python scripts/validation/prohibited_source_scan.py }

Push-Location apps/api
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\pip install -r requirements.txt -q
Run-Step "Backend unit tests" { .\.venv\Scripts\pytest -q }
Pop-Location

Push-Location apps/web
if (-not (Test-Path node_modules)) { npm install --silent }
Run-Step "Frontend build" { npm run build }
Pop-Location

Write-Host "`nChecking health endpoints (requires running stack)..."
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "API health: $($health.status)"
    $ready = Invoke-RestMethod -Uri "http://localhost:8000/ready" -TimeoutSec 5
    Write-Host "API ready: $($ready.status)"
} catch {
    Write-Host "Stack not running or not ready yet. Start with Start-Aarohan.ps1 for full E2E."
}

Write-Host "`nLocal validation complete."
