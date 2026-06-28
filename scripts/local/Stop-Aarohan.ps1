#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root
Write-Host "Stopping Aarohan CareerOS..."
docker compose down
Write-Host "Stopped."
