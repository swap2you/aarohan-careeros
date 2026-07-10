#Requires -Version 5.1
<#
.SYNOPSIS
  Invoke docker compose for the isolated test stack (project: aarohan-careeros-test).
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"

if (-not $PSScriptRoot) {
    throw "Invoke-AarohanTestCompose must be dot-sourced or run from scripts/local."
}

$script:AarohanRepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

function Import-AarohanTestEnv {
    param([string]$Root = $script:AarohanRepoRoot)
    . (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
    Import-AarohanRepoEnvLocal -Root $Root

    if ([string]::IsNullOrWhiteSpace($env:E2E_POSTGRES_PASSWORD)) {
        throw "E2E_POSTGRES_PASSWORD missing in .env.local. Run: pwsh scripts/local/Sync-EnvLocal.ps1 -GenerateMissing"
    }
    if ([string]::IsNullOrWhiteSpace($env:AAROHAN_E2E_DB_IDENTITY_UUID)) {
        throw "AAROHAN_E2E_DB_IDENTITY_UUID missing in .env.local. Run: pwsh scripts/local/Sync-EnvLocal.ps1 -GenerateMissing"
    }
    if ([string]::IsNullOrWhiteSpace($env:E2E_MIGRATE_PASSWORD)) {
        throw "E2E_MIGRATE_PASSWORD missing in .env.local. Run: pwsh scripts/local/Sync-EnvLocal.ps1 -GenerateMissing"
    }
    if ([string]::IsNullOrWhiteSpace($env:E2E_RUNTIME_PASSWORD)) {
        throw "E2E_RUNTIME_PASSWORD missing in .env.local. Run: pwsh scripts/local/Sync-EnvLocal.ps1 -GenerateMissing"
    }
}

function Invoke-AarohanTestCompose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$ComposeArgs
    )
    Set-Location $script:AarohanRepoRoot
    Import-AarohanTestEnv
    $envFile = Join-Path $script:AarohanRepoRoot ".env.local"
    $composeFile = Join-Path $script:AarohanRepoRoot "docker-compose.test.yml"
    & docker compose -p aarohan-careeros-test --env-file $envFile -f $composeFile @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose test stack failed (exit $LASTEXITCODE)"
    }
}

if ($ComposeArgs -and $ComposeArgs.Count -gt 0) {
    Invoke-AarohanTestCompose @ComposeArgs
}
