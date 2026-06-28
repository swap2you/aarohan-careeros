#Requires -Version 5.1
param([string]$OutputDir = "")

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

$dest = if ($OutputDir) { $OutputDir } else { Join-Path $Root "artifacts\backups" }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $dest "career_os_$stamp.sql"

function Get-SecretValue {
    param([string]$Name)
    try {
        Import-Module Microsoft.PowerShell.SecretManagement -ErrorAction Stop
        return Get-Secret -Name $Name -AsPlainText -ErrorAction Stop
    } catch { return $env:POSTGRES_PASSWORD }
}

$password = Get-SecretValue POSTGRES_PASSWORD
if (-not $password) { throw "POSTGRES_PASSWORD not available." }

docker compose exec -T postgres pg_dump -U career_os career_os > $outFile
Write-Host "Backup written to $outFile"
