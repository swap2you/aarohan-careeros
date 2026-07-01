#Requires -Version 5.1
<#
.SYNOPSIS
  Load Aarohan runtime configuration from repo .env.local or optional SecretStore.
#>
param(
    [ValidateSet("RepoEnvLocal", "SecretStore", "LegacyFile")]
    [string]$Mode = "RepoEnvLocal",
    [string]$LocalPath = ""
)

$script:RequiredSecretNames = @(
    "APP_SECRET",
    "POSTGRES_PASSWORD",
    "TOKEN_ENCRYPTION_KEY",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD"
)

$script:OptionalSecretNames = @(
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_OAUTH_CLIENT_JSON_PATH",
    "GOOGLE_DRIVE_ROOT_FOLDER_ID",
    "GOOGLE_OAUTH_REDIRECT_URI",
    "CAREER_GMAIL_ADDRESS",
    "TEST_EMAIL_ALLOWLIST",
    "AI_API_KEY",
    "OPENAI_API_KEY",
    "N8N_ENCRYPTION_KEY",
    "ADZUNA_APP_ID",
    "ADZUNA_APP_KEY",
    "JOOBLE_API_KEY",
    "USAJOBS_API_KEY",
    "USAJOBS_USER_EMAIL",
    "E2E_TEST_PASSWORD",
    "LOCAL_DEV_AUTH_BYPASS",
    "APP_ENV"
)

function Import-AarohanLocalEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw "Env file not found: $Path`nCopy .env.local.example to .env.local and fill in required values."
    }
    Get-Content $Path | Where-Object { $_ -match '^\s*[^#;]' -and $_ -match '=' } | ForEach-Object {
        $n, $v = $_ -split '=', 2
        $name = $n.Trim()
        $value = $v.Trim().Trim('"').Trim("'")
        if ($name) { Set-Item -Path "env:$name" -Value $value }
    }
}

function Get-AarohanSecretStoreValue {
    param([string]$Name, [string]$Default = "")
    try {
        Import-Module Microsoft.PowerShell.SecretManagement -ErrorAction Stop
        $value = Get-Secret -Name $Name -AsPlainText -ErrorAction Stop
        if ($value) { return $value }
    } catch {}
    return $Default
}

function Import-AarohanSecrets {
    param(
        [ValidateSet("RepoEnvLocal", "SecretStore", "LegacyFile")]
        [string]$Mode = "RepoEnvLocal",
        [string]$LocalPath = ""
    )
    $root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    if (-not $LocalPath) {
        if ($Mode -eq "LegacyFile") {
            $LocalPath = "C:\AarohanSecrets\aarohan.local.env"
        } else {
            $LocalPath = Join-Path $root ".env.local"
        }
    }

    if ($Mode -eq "SecretStore") {
        foreach ($name in ($script:RequiredSecretNames + $script:OptionalSecretNames)) {
            $val = Get-AarohanSecretStoreValue -Name $name
            if ($val) { Set-Item -Path "env:$name" -Value $val }
        }
    } else {
        Import-AarohanLocalEnvFile -Path $LocalPath
    }

    $missing = @()
    foreach ($name in $script:RequiredSecretNames) {
        $val = [Environment]::GetEnvironmentVariable($name)
        if ([string]::IsNullOrWhiteSpace($val)) { $missing += $name }
    }
    if ($missing.Count -gt 0) {
        throw "Missing required values: $($missing -join ', '). Mode=$Mode Path=$LocalPath"
    }

    if ([string]::IsNullOrWhiteSpace($env:AI_API_KEY) -and $env:OPENAI_API_KEY) {
        $env:AI_API_KEY = $env:OPENAI_API_KEY
    }

    if ([string]::IsNullOrWhiteSpace($env:GOOGLE_OAUTH_CLIENT_JSON_PATH)) {
        $env:GOOGLE_OAUTH_CLIENT_JSON_PATH = "C:\AarohanSecrets\google-oauth-client.json"
    }
    $hostOAuthJson = $env:GOOGLE_OAUTH_CLIENT_JSON_PATH
    if ($hostOAuthJson -and -not $hostOAuthJson.StartsWith("/")) {
        $env:GOOGLE_OAUTH_SECRETS_DIR = (Split-Path -Parent $hostOAuthJson) -replace '\\', '/'
    }
    if ($env:GOOGLE_DRIVE_ROOT_FOLDER_ID) {
        $env:GOOGLE_DRIVE_FOLDER_ID = $env:GOOGLE_DRIVE_ROOT_FOLDER_ID
    }
    if (-not $env:GOOGLE_OAUTH_REDIRECT_URI) {
        $env:GOOGLE_OAUTH_REDIRECT_URI = "http://localhost:8000/api/integrations/google/callback"
    }
    if (-not $env:ENABLE_EXTERNAL_EMAIL_SEND) { $env:ENABLE_EXTERNAL_EMAIL_SEND = "false" }
    if (-not $env:CORS_ORIGINS) { $env:CORS_ORIGINS = "http://localhost:3000" }
    if (-not $env:APP_ENV) { $env:APP_ENV = "local" }
    if (-not $env:LOCAL_DEV_AUTH_BYPASS) { $env:LOCAL_DEV_AUTH_BYPASS = "true" }
    if (-not $env:SCHEDULING_ENABLED) { $env:SCHEDULING_ENABLED = "false" }
    if (-not $env:OAUTH_FIXTURE_MODE) { $env:OAUTH_FIXTURE_MODE = "false" }

    $env:DATABASE_URL = "postgresql+psycopg://career_os:$($env:POSTGRES_PASSWORD)@localhost:5432/career_os"
}

function Test-AarohanSecretConfigured {
    param([string]$Name)
    return -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name))
}
