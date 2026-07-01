#Requires -Version 5.1
param(
    [switch]$Detached,
    [ValidateSet("LocalFile", "SecretStore")]
    [string]$SecretsMode = "LocalFile",
    [string]$LocalSecretsPath = "C:\AarohanSecrets\aarohan.local.env",
    [switch]$WithN8n
)

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
. (Join-Path $PSScriptRoot "Import-LocalSecrets.ps1")
Import-AarohanSecrets -Mode $SecretsMode -LocalPath $LocalSecretsPath

$hostOAuthJson = Join-Path ($env:GOOGLE_OAUTH_SECRETS_DIR -replace '/', '\') "google-oauth-client.json"
if (-not (Test-Path $hostOAuthJson)) {
    Write-Warning "OAuth JSON not found at $hostOAuthJson. Live Google OAuth unavailable until file exists."
}

if ($WithN8n -and [string]::IsNullOrWhiteSpace($env:N8N_ENCRYPTION_KEY)) {
    throw "N8N_ENCRYPTION_KEY required when using -WithN8n. Add to $LocalSecretsPath"
}

$composeArgs = @("compose")
if ($WithN8n) {
    $composeArgs += "--profile", "n8n"
}
$composeArgs += "up", "--build"
if ($Detached) { $composeArgs += "-d" }

Write-Host "Starting Aarohan CareerOS (secrets=$SecretsMode, n8n=$WithN8n)..."
& docker @composeArgs
if ($LASTEXITCODE -ne 0) { throw "docker compose failed (exit $LASTEXITCODE)" }

if ($Detached) {
    Write-Host "Waiting for health checks..."
    $deadline = (Get-Date).AddMinutes(3)
    $apiOk = $false
    $webOk = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $h = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 3
            if ($h.status -eq "ok") { $apiOk = $true }
        } catch {}
        try {
            $w = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 3 -UseBasicParsing
            if ($w.StatusCode -eq 200) { $webOk = $true }
        } catch {}
        if ($apiOk -and $webOk) { break }
        Start-Sleep -Seconds 3
    }
    Write-Host ""
    Write-Host "=== Aarohan CareerOS ==="
    Write-Host "Web:  http://localhost:3000"
    Write-Host "API:  http://localhost:8000/health"
    if ($WithN8n) { Write-Host "n8n:  http://localhost:5678" }
    Write-Host "API healthy: $apiOk | Web healthy: $webOk"
    if (-not $apiOk -or -not $webOk) {
        Write-Warning "One or more services not healthy yet — check: docker compose ps"
    }
}
