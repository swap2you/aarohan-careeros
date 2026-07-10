#Requires -Version 5.1
<#
.SYNOPSIS
  Invoke docker compose for the isolated owner-candidate runtime (project: aarohan-careeros-candidate).
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"

if (-not $PSScriptRoot) {
    throw "Invoke-AarohanCandidateCompose must be dot-sourced or run from scripts/local."
}

$script:AarohanRepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

function Import-AarohanCandidateEnv {
    param([string]$Root = $script:AarohanRepoRoot)
    . (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
    Import-AarohanRepoEnvLocal -Root $Root

    $required = @(
        "CANDIDATE_MIGRATE_PASSWORD",
        "CANDIDATE_RUNTIME_PASSWORD",
        "AAROHAN_OWNER_CANDIDATE_DB_IDENTITY_UUID"
    )
    foreach ($name in $required) {
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
            throw "Missing required value in .env.local: $name. Run Sync-EnvLocal or Phase 3 rework provisioning."
        }
    }
}

function Invoke-AarohanCandidateCompose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$ComposeArgs
    )
    Set-Location $script:AarohanRepoRoot
    Import-AarohanCandidateEnv
    $envFile = Join-Path $script:AarohanRepoRoot ".env.local"
    $composeFile = Join-Path $script:AarohanRepoRoot "docker-compose.candidate.yml"
    & docker compose -p aarohan-careeros-candidate --env-file $envFile -f $composeFile @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose candidate stack failed (exit $LASTEXITCODE)"
    }
}

if ($ComposeArgs -and $ComposeArgs.Count -gt 0) {
    Invoke-AarohanCandidateCompose @ComposeArgs
}
