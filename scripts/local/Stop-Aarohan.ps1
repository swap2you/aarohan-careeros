#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root
Write-Host "Stopping Aarohan CareerOS..."

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
if (Test-Path (Join-Path $Root ".env.local")) {
    Invoke-AarohanCompose down
} else {
    docker compose down
}
Write-Host "Stopped."
