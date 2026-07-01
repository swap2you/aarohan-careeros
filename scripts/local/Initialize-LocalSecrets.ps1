#Requires -Version 5.1
<#
.SYNOPSIS
  Create or update C:\AarohanSecrets\aarohan.local.env from SecretStore (one-time migration).
.DESCRIPTION
  Never prints secret values. Creates backup and restricts file to current user.
#>
param(
    [string]$OutputPath = "C:\AarohanSecrets\aarohan.local.env",
    [switch]$FromSecretStore,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Import-LocalSecrets.ps1")

$names = $script:RequiredSecretNames + $script:OptionalSecretNames
$dir = Split-Path $OutputPath -Parent
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

if ((Test-Path $OutputPath) -and -not $Force) {
    Write-Host "Secrets file already exists: $OutputPath"
    Write-Host "Use -Force to overwrite from SecretStore, or edit the file manually."
    exit 0
}

$lines = @(
    "# Aarohan CareerOS local runtime secrets — DO NOT COMMIT",
    "# Generated: $(Get-Date -Format o)",
    ""
)

function Read-SecretStoreValue {
    param([string]$Name)
    if (-not $FromSecretStore) { return $null }
    return Get-AarohanSecretStoreValue -Name $Name
}

foreach ($name in $names) {
    $value = Read-SecretStoreValue -Name $name
    if ([string]::IsNullOrWhiteSpace($value)) {
        $lines += "# $name="
        continue
    }
    $escaped = $value -replace '"', '\"'
    $lines += "$name=`"$escaped`""
}

if (Test-Path $OutputPath) {
    $backup = "$OutputPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $OutputPath $backup
    Write-Host "Backup: $backup"
}

$lines | Set-Content -Path $OutputPath -Encoding UTF8

# Restrict to current user (best effort on Windows)
try {
    icacls $OutputPath /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
} catch {
    Write-Warning "Could not set NTFS ACL on secrets file: $_"
}

$missing = @()
foreach ($name in $script:RequiredSecretNames) {
    $content = Get-Content $OutputPath -Raw
    if ($content -notmatch "(?m)^$name=.+") { $missing += $name }
}

Write-Host "Wrote: $OutputPath"
if ($missing.Count -gt 0) {
    Write-Warning "Required variables still empty — edit file and set: $($missing -join ', ')"
} else {
    Write-Host "All required variable names present."
}
Write-Host "Start stack: pwsh scripts/local/Start-Aarohan.ps1 -Detached"
