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
    Write-Host "Use -Force to regenerate (SecretStore + .env.local merge), or edit the file manually."
    Write-Host "Required keys must be uncommented NAME=`"value`" lines — commented-only templates are not loaded."
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

# Merge non-secret connector/AI keys from repo .env.local when present (values never printed).
$envLocal = Join-Path $Root ".env.local"
if (Test-Path $envLocal) {
    $map = @{
        OPENAI_API_KEY           = "AI_API_KEY"
        ADZUNA_APP_ID            = "ADZUNA_APP_ID"
        ADZUNA_APP_KEY           = "ADZUNA_APP_KEY"
        JOOBLE_API_KEY           = "JOOBLE_API_KEY"
        USAJOBS_API_KEY          = "USAJOBS_API_KEY"
        USAJOBS_USER_AGENT       = "USAJOBS_USER_EMAIL"
        CAREER_GMAIL_ADDRESS     = "CAREER_GMAIL_ADDRESS"
        GOOGLE_DRIVE_ROOT_FOLDER_ID = "GOOGLE_DRIVE_ROOT_FOLDER_ID"
        TEST_EMAIL_ALLOWLIST     = "TEST_EMAIL_ALLOWLIST"
        N8N_ENCRYPTION_KEY       = "N8N_ENCRYPTION_KEY"
    }
    $merged = @{}
    foreach ($line in $lines) {
        if ($line -match '^\s*#?\s*([A-Z_][A-Z0-9_]*)=') {
            $merged[$matches[1]] = $line
        }
    }
    Get-Content $envLocal | Where-Object { $_ -match '^\s*[^#]' -and $_ -match '=' } | ForEach-Object {
        $n, $v = $_ -split '=', 2
        $key = $n.Trim()
        if (-not $map.ContainsKey($key)) { return }
        $target = $map[$key]
        $val = $v.Trim().Trim('"').Trim("'")
        if ([string]::IsNullOrWhiteSpace($val)) { return }
        $escaped = $val -replace '"', '\"'
        $merged[$target] = "$target=`"$escaped`""
    }
    $header = $lines | Where-Object { $_ -notmatch '^\s*#?\s*[A-Z_][A-Z0-9_]*=' }
    $lines = @($header) + ($names | ForEach-Object { if ($merged.ContainsKey($_)) { $merged[$_] } else { "# $_=" } })
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
