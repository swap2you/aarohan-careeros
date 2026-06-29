#Requires -Version 5.1
param([switch]$Detached)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

function Import-EnvLocalFile {
    $path = Join-Path $Root ".env.local"
    if (-not (Test-Path $path)) { return }
    Write-Host "Loading non-secret config from .env.local"
    Get-Content $path | Where-Object { $_ -match '^\s*[^#]' -and $_ -match '=' } | ForEach-Object {
        $n, $v = $_ -split '=', 2
        $name = $n.Trim()
        $value = $v.Trim().Trim('"').Trim("'")
        if ($name) { Set-Item -Path "env:$name" -Value $value }
    }
}

Import-EnvLocalFile

function Get-SecretValue {
    param([string]$Name, [string]$Default = "")
    try {
        Import-Module Microsoft.PowerShell.SecretManagement -ErrorAction Stop
        $value = Get-Secret -Name $Name -AsPlainText -ErrorAction Stop
        if ($value) { return $value }
    } catch {}
    return $Default
}

$required = @("APP_SECRET", "POSTGRES_PASSWORD", "TOKEN_ENCRYPTION_KEY", "ADMIN_EMAIL", "ADMIN_PASSWORD")
foreach ($name in $required) {
    $val = Get-SecretValue -Name $name
    if ([string]::IsNullOrWhiteSpace($val)) {
        throw "Missing required secret '$name'. Run scripts/local/Initialize-AarohanSecrets.ps1 first."
    }
}

$env:APP_SECRET = Get-SecretValue -Name APP_SECRET
$env:POSTGRES_PASSWORD = Get-SecretValue -Name POSTGRES_PASSWORD
$env:TOKEN_ENCRYPTION_KEY = Get-SecretValue -Name TOKEN_ENCRYPTION_KEY
$env:ADMIN_EMAIL = Get-SecretValue -Name ADMIN_EMAIL
$env:ADMIN_PASSWORD = Get-SecretValue -Name ADMIN_PASSWORD
$env:GOOGLE_CLIENT_ID = Get-SecretValue -Name GOOGLE_CLIENT_ID
$env:GOOGLE_CLIENT_SECRET = Get-SecretValue -Name GOOGLE_CLIENT_SECRET
$hostOAuthJson = Get-SecretValue -Name GOOGLE_OAUTH_CLIENT_JSON_PATH "C:\AarohanSecrets\google-oauth-client.json"
$env:GOOGLE_OAUTH_SECRETS_DIR = (Split-Path -Parent $hostOAuthJson) -replace '\\', '/'
if (-not (Test-Path $hostOAuthJson)) {
    Write-Warning "OAuth JSON not found at $hostOAuthJson. Live Google OAuth will fail until the file exists."
}
# Container path (Linux) — host file is bind-mounted to /run/secrets/
$env:GOOGLE_OAUTH_CLIENT_JSON_PATH = "/run/secrets/google-oauth-client.json"
$env:GOOGLE_DRIVE_ROOT_FOLDER_ID = Get-SecretValue -Name GOOGLE_DRIVE_ROOT_FOLDER_ID "1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr"
$env:GOOGLE_DRIVE_FOLDER_ID = $env:GOOGLE_DRIVE_ROOT_FOLDER_ID
$env:GOOGLE_OAUTH_REDIRECT_URI = Get-SecretValue -Name GOOGLE_OAUTH_REDIRECT_URI "http://localhost:8000/api/integrations/google/callback"
$env:CAREER_GMAIL_ADDRESS = Get-SecretValue -Name CAREER_GMAIL_ADDRESS "swapnilpatil.tech@gmail.com"
$env:ENABLE_EXTERNAL_EMAIL_SEND = "false"
$env:TEST_EMAIL_ALLOWLIST = Get-SecretValue -Name TEST_EMAIL_ALLOWLIST "swap2you@gmail.com,patilsaci@gmail.com,sriswapnilpatil@gmail.com,patilswapnilqa@gmail.com"
$env:AI_API_KEY = Get-SecretValue -Name AI_API_KEY
$env:N8N_ENCRYPTION_KEY = Get-SecretValue -Name N8N_ENCRYPTION_KEY
if ([string]::IsNullOrWhiteSpace($env:N8N_ENCRYPTION_KEY)) {
    $env:N8N_ENCRYPTION_KEY = -join ((48..57 + 65..90 + 97..122 | Get-Random -Count 32 | ForEach-Object { [char]$_ }))
    Write-Host "Generated ephemeral N8N_ENCRYPTION_KEY for this session."
}
$env:DATABASE_URL = "postgresql+psycopg://career_os:$($env:POSTGRES_PASSWORD)@localhost:5432/career_os"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:APP_ENV = "development"
$env:SCHEDULING_ENABLED = "false"

Write-Host "Starting Aarohan CareerOS (local-first, schedules disabled)..."
if ($Detached) {
    docker compose up --build -d
} else {
    docker compose up --build
}
