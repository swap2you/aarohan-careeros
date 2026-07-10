#Requires -Version 5.1
<#
.SYNOPSIS
  Ensure repo .env.local has required runtime secrets (merge from legacy file or generate).

.DESCRIPTION
  Primary config file for Start-Aarohan.ps1 is .env.local in the repo root.
  If required keys are empty, this script merges from:
    1. C:\AarohanSecrets\aarohan.local.env (legacy)
    2. PowerShell SecretStore (optional -UseSecretStore)

  Never prints secret values.

.EXAMPLE
  pwsh scripts/local/Sync-EnvLocal.ps1
  pwsh scripts/local/Sync-EnvLocal.ps1 -UseSecretStore
#>
param(
    [string]$LegacyPath = "C:\AarohanSecrets\aarohan.local.env",
    [switch]$UseSecretStore,
    [switch]$GenerateMissing
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Import-LocalSecrets.ps1")

$target = Join-Path $Root ".env.local"
$example = Join-Path $Root ".env.local.example"

if (-not (Test-Path $target)) {
    if (Test-Path $example) {
        Copy-Item $example $target
        Write-Host "Created .env.local from .env.local.example"
    } else {
        throw ".env.local missing and no .env.local.example template found."
    }
}

function Read-EnvFileMap {
    param([string]$Path)
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
        $n, $v = $_ -split '=', 2
        $name = $n.Trim()
        if (-not $name) { return }
        $map[$name] = $v.Trim().Trim('"').Trim("'")
    }
    return $map
}

function Write-EnvFileMap {
    param(
        [string]$Path,
        [hashtable]$Map,
        [string[]]$Order
    )
    $existingLines = if (Test-Path $Path) { Get-Content $Path } else { @() }
    $written = @{}
    $out = New-Object System.Collections.Generic.List[string]

    foreach ($line in $existingLines) {
        if ($line -match '^\s*([A-Z_][A-Z0-9_]*)\s*=') {
            $key = $matches[1]
            if ($Map.ContainsKey($key)) {
                $val = $Map[$key]
                if (-not [string]::IsNullOrWhiteSpace($val)) {
                    if ($val -match '[\s#"]') {
                        $escaped = $val -replace '"', '\"'
                        $out.Add("$key=`"$escaped`"")
                    } else {
                        $out.Add("$key=$val")
                    }
                    $written[$key] = $true
                    continue
                }
            }
        }
        $out.Add($line)
    }

    foreach ($key in $Order) {
        if ($written.ContainsKey($key)) { continue }
        if (-not $Map.ContainsKey($key)) { continue }
        $val = $Map[$key]
        if ([string]::IsNullOrWhiteSpace($val)) { continue }
        if ($val -match '[\s#"]') {
            $escaped = $val -replace '"', '\"'
            $out.Add("$key=`"$escaped`"")
        } else {
            $out.Add("$key=$val")
        }
        $written[$key] = $true
    }

    foreach ($key in ($Map.Keys | Sort-Object)) {
        if ($written.ContainsKey($key)) { continue }
        $val = $Map[$key]
        if ([string]::IsNullOrWhiteSpace($val)) { continue }
        if ($val -match '[\s#"]') {
            $escaped = $val -replace '"', '\"'
            $out.Add("$key=`"$escaped`"")
        } else {
            $out.Add("$key=$val")
        }
    }

    $out | Set-Content -Path $Path -Encoding UTF8
}

function New-RandomSecret {
    param([int]$Length = 48)
    $raw = ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
    if ($raw.Length -lt $Length) {
        $raw += [guid]::NewGuid().ToString('N')
    }
    return $raw.Substring(0, [Math]::Min($Length, $raw.Length))
}

function New-UuidV4 {
    return [guid]::NewGuid().ToString()
}

$required = @("APP_SECRET", "POSTGRES_PASSWORD", "TOKEN_ENCRYPTION_KEY", "ADMIN_EMAIL", "ADMIN_PASSWORD")
$isolationKeys = @(
    "E2E_POSTGRES_PASSWORD",
    "E2E_MIGRATE_PASSWORD",
    "E2E_RUNTIME_PASSWORD",
    "POSTGRES_MIGRATE_PASSWORD",
    "POSTGRES_RUNTIME_PASSWORD",
    "AAROHAN_OWNER_DB_IDENTITY_UUID",
    "AAROHAN_E2E_DB_IDENTITY_UUID",
    "AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID",
    "CANDIDATE_MIGRATE_PASSWORD",
    "CANDIDATE_RUNTIME_PASSWORD",
    "AAROHAN_DESTRUCTIVE_TOKEN"
)
$defaults = @{
    APP_ENV                 = "local"
    LOCAL_DEV_AUTH_BYPASS   = "true"
    OAUTH_FIXTURE_MODE      = "false"
    ENABLE_EXTERNAL_EMAIL_SEND = "false"
}

$targetMap = Read-EnvFileMap -Path $target
foreach ($k in $defaults.Keys) {
    if ([string]::IsNullOrWhiteSpace($targetMap[$k])) {
        $targetMap[$k] = $defaults[$k]
    }
}

$legacyMap = Read-EnvFileMap -Path $LegacyPath
foreach ($key in ($required + $script:OptionalSecretNames)) {
    if (-not [string]::IsNullOrWhiteSpace($targetMap[$key])) { continue }
    if ($legacyMap.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace($legacyMap[$key])) {
        $targetMap[$key] = $legacyMap[$key]
    }
}

if ($UseSecretStore) {
    foreach ($key in ($required + $script:OptionalSecretNames)) {
        if (-not [string]::IsNullOrWhiteSpace($targetMap[$key])) { continue }
        $val = Get-AarohanSecretStoreValue -Name $key
        if ($val) { $targetMap[$key] = $val }
    }
}

if ($GenerateMissing) {
    if ([string]::IsNullOrWhiteSpace($targetMap.APP_SECRET)) {
        $targetMap.APP_SECRET = New-RandomSecret -Length 48
        Write-Host "Generated APP_SECRET"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.POSTGRES_PASSWORD)) {
        $targetMap.POSTGRES_PASSWORD = New-RandomSecret -Length 32
        Write-Host "Generated POSTGRES_PASSWORD"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.TOKEN_ENCRYPTION_KEY)) {
        $targetMap.TOKEN_ENCRYPTION_KEY = New-RandomSecret -Length 32
        Write-Host "Generated TOKEN_ENCRYPTION_KEY"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.E2E_POSTGRES_PASSWORD)) {
        $targetMap.E2E_POSTGRES_PASSWORD = New-RandomSecret -Length 32
        Write-Host "Generated E2E_POSTGRES_PASSWORD"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.POSTGRES_MIGRATE_PASSWORD)) {
        $targetMap.POSTGRES_MIGRATE_PASSWORD = New-RandomSecret -Length 32
        Write-Host "Generated POSTGRES_MIGRATE_PASSWORD"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.POSTGRES_RUNTIME_PASSWORD)) {
        $targetMap.POSTGRES_RUNTIME_PASSWORD = New-RandomSecret -Length 32
        Write-Host "Generated POSTGRES_RUNTIME_PASSWORD"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.E2E_MIGRATE_PASSWORD)) {
        $targetMap.E2E_MIGRATE_PASSWORD = New-RandomSecret -Length 32
        Write-Host "Generated E2E_MIGRATE_PASSWORD"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.E2E_RUNTIME_PASSWORD)) {
        $targetMap.E2E_RUNTIME_PASSWORD = New-RandomSecret -Length 32
        Write-Host "Generated E2E_RUNTIME_PASSWORD"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.AAROHAN_OWNER_DB_IDENTITY_UUID)) {
        $targetMap.AAROHAN_OWNER_DB_IDENTITY_UUID = New-UuidV4
        Write-Host "Generated AAROHAN_OWNER_DB_IDENTITY_UUID"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.AAROHAN_E2E_DB_IDENTITY_UUID)) {
        $targetMap.AAROHAN_E2E_DB_IDENTITY_UUID = New-UuidV4
        Write-Host "Generated AAROHAN_E2E_DB_IDENTITY_UUID"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.CANDIDATE_MIGRATE_PASSWORD)) {
        $targetMap.CANDIDATE_MIGRATE_PASSWORD = New-RandomSecret -Length 32
        Write-Host "Generated CANDIDATE_MIGRATE_PASSWORD"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.CANDIDATE_RUNTIME_PASSWORD)) {
        $targetMap.CANDIDATE_RUNTIME_PASSWORD = New-RandomSecret -Length 32
        Write-Host "Generated CANDIDATE_RUNTIME_PASSWORD"
    }
    if ([string]::IsNullOrWhiteSpace($targetMap.AAROHAN_DESTRUCTIVE_TOKEN)) {
        $targetMap.AAROHAN_DESTRUCTIVE_TOKEN = New-RandomSecret -Length 24
        Write-Host "Generated AAROHAN_DESTRUCTIVE_TOKEN"
    }
}

if ([string]::IsNullOrWhiteSpace($targetMap.AI_API_KEY) -and $targetMap.OPENAI_API_KEY) {
    $targetMap.AI_API_KEY = $targetMap.OPENAI_API_KEY
}

Write-EnvFileMap -Path $target -Map $targetMap -Order ($required + @("APP_ENV", "LOCAL_DEV_AUTH_BYPASS") + $isolationKeys)

$missing = @()
foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace($targetMap[$name])) { $missing += $name }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Still missing in .env.local: $($missing -join ', ')"
    Write-Host "Options:"
    Write-Host "  1. Edit .env.local and set the missing keys manually"
    Write-Host "  2. If secrets exist in $LegacyPath, run: pwsh scripts/local/Sync-EnvLocal.ps1"
    Write-Host "  3. Generate crypto keys only: pwsh scripts/local/Sync-EnvLocal.ps1 -GenerateMissing"
    Write-Host "  4. Pull from SecretStore: pwsh scripts/local/Sync-EnvLocal.ps1 -UseSecretStore -GenerateMissing"
    exit 1
}

Write-Host "OK: .env.local has all required keys (values not shown)."
Write-Host "Start: pwsh scripts/local/Start-Aarohan.ps1 -Detached"
exit 0
