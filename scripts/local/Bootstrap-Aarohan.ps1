#Requires -Version 5.1
<#
.SYNOPSIS
  One-command bootstrap for Aarohan CareerOS local development.
#>
param([switch]$SkipDockerCheck)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

function Test-CommandExists($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Require-Command {
    param([string]$Name, [string]$InstallHint)
    if (-not (Test-CommandExists $Name)) {
        throw "Missing prerequisite '$Name'. $InstallHint"
    }
}

Write-Host "=== Aarohan Bootstrap ==="

Require-Command git "Install Git from https://git-scm.com/download/win"
Require-Command python "Install Python 3.12+ from https://www.python.org/downloads/"
Require-Command node "Install Node.js 20+ from https://nodejs.org/"
Require-Command npm "Install Node.js (includes npm)"
Require-Command pwsh "Install PowerShell 7+"

Write-Host "git: $(git --version)"
Write-Host "python: $(python --version)"
Write-Host "node: $(node --version)"
Write-Host "npm: $(npm --version)"
Write-Host "pwsh: $(pwsh --version)"

if (-not $SkipDockerCheck) {
    if (Test-CommandExists docker) {
        Write-Host "docker: $(docker --version)"
        Write-Host "compose: $(docker compose version)"
    } else {
        Write-Warning "Docker not found. Install Docker Desktop or rerun with -SkipDockerCheck for direct-dev mode."
        Write-Host "Install: choco install docker-desktop -y  OR  winget install -e --id Docker.DockerDesktop"
    }
}

if (-not (Test-Path ".env.local")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env.local"
        Write-Host "Created .env.local from .env.example (no secrets)."
    }
}

$oauthPath = "C:\AarohanSecrets\google-oauth-client.json"
if (-not (Test-Path $oauthPath)) {
    Write-Warning "OAuth JSON not found at $oauthPath. Google live mode will be unavailable until placed."
} else {
    Write-Host "OAuth JSON path verified (file exists)."
}

& "$PSScriptRoot\Initialize-AarohanSecrets.ps1"

Push-Location apps/api
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\pip install -r requirements.txt -q
Pop-Location

Push-Location apps/web
if (-not (Test-Path node_modules)) { npm install --silent }
Pop-Location

Write-Host ""
Write-Host "Bootstrap complete. Next:"
Write-Host "  pwsh scripts/local/Start-Aarohan.ps1 -Detached"
Write-Host "  pwsh scripts/local/Test-Aarohan.ps1"
