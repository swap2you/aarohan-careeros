#Requires -Version 5.1
<#
.SYNOPSIS
  Load repo .env.local and invoke docker compose with consistent env substitution.
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"

if (-not $PSScriptRoot) {
    throw "Invoke-AarohanCompose must be dot-sourced or run from scripts/local."
}

$script:AarohanRepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

function Import-AarohanLegacySecretsFile {
    param([string]$Path = "C:\AarohanSecrets\aarohan.local.env")
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | Where-Object { $_ -match '^\s*[^#;]' -and $_ -match '=' } | ForEach-Object {
        $n, $v = $_ -split '=', 2
        $name = $n.Trim()
        $value = $v.Trim().Trim('"').Trim("'")
        if ($name -and [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
            Set-Item -Path "env:$name" -Value $value
        }
    }
}

function Import-AarohanRepoEnvLocal {
    param([string]$Root = $script:AarohanRepoRoot)
    $path = Join-Path $Root ".env.local"
    if (-not (Test-Path $path)) {
        $example = Join-Path $Root ".env.local.example"
        if (Test-Path $example) {
            throw ".env.local not found. Run: pwsh scripts/local/Sync-EnvLocal.ps1"
        }
        throw ".env.local not found at $path"
    }
    Get-Content $path | Where-Object { $_ -match '^\s*[^#;]' -and $_ -match '=' } | ForEach-Object {
        $n, $v = $_ -split '=', 2
        $name = $n.Trim()
        $value = $v.Trim().Trim('"').Trim("'")
        if ($name) { Set-Item -Path "env:$name" -Value $value }
    }
    Import-AarohanLegacySecretsFile
    if ([string]::IsNullOrWhiteSpace($env:APP_ENV)) { $env:APP_ENV = "local" }
    if ([string]::IsNullOrWhiteSpace($env:LOCAL_DEV_AUTH_BYPASS)) { $env:LOCAL_DEV_AUTH_BYPASS = "true" }
    if ([string]::IsNullOrWhiteSpace($env:OAUTH_FIXTURE_MODE)) { $env:OAUTH_FIXTURE_MODE = "false" }
    if ([string]::IsNullOrWhiteSpace($env:ENABLE_EXTERNAL_EMAIL_SEND)) { $env:ENABLE_EXTERNAL_EMAIL_SEND = "false" }
    if ([string]::IsNullOrWhiteSpace($env:CORS_ORIGINS)) { $env:CORS_ORIGINS = "http://localhost:3000" }
    if ([string]::IsNullOrWhiteSpace($env:SCHEDULING_ENABLED)) { $env:SCHEDULING_ENABLED = "false" }
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
}

function Invoke-AarohanCompose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
    Set-Location $script:AarohanRepoRoot
    Import-AarohanRepoEnvLocal
    $envFile = Join-Path $script:AarohanRepoRoot ".env.local"
    $missing = @()
    foreach ($name in @("APP_SECRET", "POSTGRES_PASSWORD", "TOKEN_ENCRYPTION_KEY", "ADMIN_EMAIL", "ADMIN_PASSWORD", "AAROHAN_OWNER_DB_IDENTITY_UUID")) {
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
            $missing += $name
        }
    }
    if ($missing.Count -gt 0) {
        throw @"
Missing required values in .env.local: $($missing -join ', ')

Fix (pick one):
  pwsh scripts/local/Sync-EnvLocal.ps1
  pwsh scripts/local/Sync-EnvLocal.ps1 -GenerateMissing
  pwsh scripts/local/Sync-EnvLocal.ps1 -UseSecretStore -GenerateMissing

Then start again:
  pwsh scripts/local/Start-Aarohan.ps1 -Detached
"@
    }
    & docker compose --env-file $envFile @Args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed (exit $LASTEXITCODE)"
    }
}

function Invoke-AarohanComposeExec {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputScript,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
    Set-Location $script:AarohanRepoRoot
    Import-AarohanRepoEnvLocal
    $envFile = Join-Path $script:AarohanRepoRoot ".env.local"
    $InputScript | & docker compose --env-file $envFile exec @Args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose exec failed (exit $LASTEXITCODE)"
    }
}

if ($ComposeArgs -and $ComposeArgs.Count -gt 0) {
    Invoke-AarohanCompose @ComposeArgs
}
