#Requires -Version 5.1
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

if (-not (Test-Path $BackupFile)) { throw "Backup file not found: $BackupFile" }

$confirm = Read-Host "Restore will overwrite career_os database. Type RESTORE to continue"
if ($confirm -ne "RESTORE") { throw "Restore cancelled." }

Get-Content $BackupFile | docker compose exec -T postgres psql -U career_os -d career_os
Write-Host "Restore complete from $BackupFile"
