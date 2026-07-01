#Requires -Version 5.1
<#
.SYNOPSIS
  Start isolated E2E API/web stack on ports 8001/3001 with career_os_e2e database.
#>
param([switch]$Detached)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root
$envFile = Join-Path $Root ".env.local"

docker compose --env-file $envFile up -d postgres
Start-Sleep -Seconds 3

$exists = docker compose --env-file $envFile exec -T postgres psql -U career_os -d postgres -t -A -c "SELECT 1 FROM pg_database WHERE datname='career_os_e2e'"
if (-not ($exists -match "1")) {
    Write-Host "Creating isolated database career_os_e2e"
    docker compose --env-file $envFile exec -T postgres psql -U career_os -d postgres -c "CREATE DATABASE career_os_e2e OWNER career_os;"
}

Write-Host "Running migrations on career_os_e2e"
docker compose --env-file $envFile run --rm -e "DATABASE_URL=postgresql+psycopg://career_os:$env:POSTGRES_PASSWORD@postgres:5432/career_os_e2e" api alembic upgrade head

$e2ePassword = $env:E2E_TEST_PASSWORD
if (-not $e2ePassword) {
    $e2ePassword = "E2eTest" + "Pass123!"
}

$upArgs = @("--env-file", $envFile, "-f", "docker-compose.yml", "-f", "docker-compose.e2e.yml", "up", "-d", "api-e2e", "web-e2e")
docker compose @upArgs
Start-Sleep -Seconds 8

docker compose --env-file $envFile run --rm `
    -e "DATABASE_URL=postgresql+psycopg://career_os:$env:POSTGRES_PASSWORD@postgres:5432/career_os_e2e" `
    -e "APP_SECRET=$env:APP_SECRET" `
    -e "TOKEN_ENCRYPTION_KEY=$env:TOKEN_ENCRYPTION_KEY" `
    -e "E2E_TEST_PASSWORD=$e2ePassword" `
    api python scripts/ensure_e2e_user.py

Write-Host "E2E stack ready:"
Write-Host "  API: http://127.0.0.1:8001"
Write-Host "  Web: http://127.0.0.1:3001"
Write-Host "  DB:  career_os_e2e (isolated from owner career_os)"
