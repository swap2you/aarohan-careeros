#Requires -Version 5.1
<#
.SYNOPSIS
  Stop then start Aarohan CareerOS (cold restart, keeps database volumes).
#>
param([switch]$Foreground)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

& "$PSScriptRoot\Stop-Aarohan.ps1"
Start-Sleep -Seconds 3
if ($Foreground) {
    & "$PSScriptRoot\Start-Aarohan.ps1"
} else {
    & "$PSScriptRoot\Start-Aarohan.ps1" -Detached
}
