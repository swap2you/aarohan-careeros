#Requires -Version 5.1
param(
    [switch]$Detached,
    [switch]$UseSecretStore,
    [string]$LocalSecretsPath = "",
    [switch]$WithN8n
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")

if ($UseSecretStore) {
    . (Join-Path $PSScriptRoot "Import-LocalSecrets.ps1")
    Import-AarohanSecrets -Mode SecretStore
} else {
    $syncArgs = @("-NoProfile", "-File", (Join-Path $PSScriptRoot "Sync-EnvLocal.ps1"))
    if ($env:AAROHAN_GENERATE_MISSING_SECRETS -eq "true") { $syncArgs += "-GenerateMissing" }
    & pwsh @syncArgs
    if ($LASTEXITCODE -ne 0) { throw "Cannot start — fix .env.local first (see Sync-EnvLocal.ps1 output)." }
    Import-AarohanRepoEnvLocal -Root $Root
}

$hostOAuthJson = Join-Path ($env:GOOGLE_OAUTH_SECRETS_DIR -replace '/', '\') "google-oauth-client.json"
if (-not (Test-Path $hostOAuthJson)) {
    Write-Warning "OAuth JSON not found at $hostOAuthJson. Live Google OAuth unavailable until file exists."
}

if ($WithN8n -and [string]::IsNullOrWhiteSpace($env:N8N_ENCRYPTION_KEY)) {
    throw "N8N_ENCRYPTION_KEY required when using -WithN8n. Add to .env.local"
}

$composeArgs = @("up", "--build")
if ($WithN8n) {
    $composeArgs = @("--profile", "n8n") + $composeArgs
}
if ($Detached) { $composeArgs += "-d" }

Write-Host "Starting Aarohan CareerOS (config=.env.local, n8n=$WithN8n)..."
Invoke-AarohanCompose @composeArgs

if ($Detached) {
    Write-Host "Waiting for health checks..."
    $deadline = (Get-Date).AddMinutes(3)
    $apiOk = $false
    $webOk = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3
            if ($h.status -eq "ok") { $apiOk = $true }
        } catch {}
        try {
            $w = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -TimeoutSec 3 -UseBasicParsing
            if ($w.StatusCode -eq 200) { $webOk = $true }
        } catch {}
        if ($apiOk -and $webOk) { break }
        Start-Sleep -Seconds 3
    }
    Write-Host ""
    Write-Host "=== Aarohan CareerOS ==="
    Write-Host "Web:  http://127.0.0.1:3000"
    Write-Host "API:  http://127.0.0.1:8000/health"
    if ($WithN8n) { Write-Host "n8n:  http://127.0.0.1:5678" }
    if ($env:LOCAL_DEV_AUTH_BYPASS -eq "true") {
        Write-Host "Local admin bypass: enabled (Enter Local Admin on login)"
    }
    Write-Host "API healthy: $apiOk | Web healthy: $webOk"
    if (-not $apiOk -or -not $webOk) {
        Write-Warning "One or more services not healthy yet — check: docker compose ps"
    }
}
