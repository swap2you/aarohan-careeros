#Requires -Version 5.1
param(
    [switch]$Force,
    [switch]$Volumes
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

if (-not $Force) {
    $confirm = Read-Host "Reset will stop containers and remove data. Type RESET to continue"
    if ($confirm -ne "RESET") { throw "Reset cancelled." }
}

& "$PSScriptRoot\Stop-Aarohan.ps1" -ErrorAction SilentlyContinue

if ($Volumes) {
    docker compose down -v
    Write-Host "Removed Docker volumes."
} else {
    docker compose down
}

Write-Host "Reset complete."
