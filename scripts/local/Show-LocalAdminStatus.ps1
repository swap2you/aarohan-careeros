#Requires -Version 5.1
<#
.SYNOPSIS
  Show local admin configuration status without printing passwords.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")

try {
    Import-AarohanRepoEnvLocal -Root $Root
} catch {
    Write-Host "configured_email: (missing .env.local)"
    Write-Host "password_configured: no"
    Write-Host "local_dev_auth_bypass: unknown"
    Write-Host "app_env: unknown"
    Write-Host "database_user_exists: unknown (start API container)"
    Write-Host "e2e_user_in_owner_db: unknown"
    Write-Host "active: unknown"
    exit 1
}

$email = $env:ADMIN_EMAIL
$passwordConfigured = if ([string]::IsNullOrWhiteSpace($env:ADMIN_PASSWORD)) { "no" } else { "yes" }
$bypass = if ($env:LOCAL_DEV_AUTH_BYPASS -eq "true") { "yes" } else { "no" }
Write-Host "configured_email: $email"
Write-Host "password_configured: $passwordConfigured"
Write-Host "local_dev_auth_bypass: $bypass"
Write-Host "app_env: $($env:APP_ENV)"

$apiStatus = docker compose --env-file (Join-Path $Root ".env.local") ps api --format "{{.Status}}" 2>$null
if (-not $apiStatus -or $apiStatus -notmatch "Up") {
    Write-Host "database_user_exists: unknown (API not running)"
    Write-Host "e2e_user_in_owner_db: unknown"
    Write-Host "active: unknown"
    exit 0
}

$py = @'
import os
from app.database import SessionLocal
from app.models import User
from app.services.environment import E2E_TEST_EMAIL

email = os.environ.get("ADMIN_EMAIL", "").lower()
db = SessionLocal()
try:
    e2e = db.query(User).filter(User.email.ilike(E2E_TEST_EMAIL)).one_or_none()
    print(f"e2e_user_in_owner_db: {'yes' if e2e and e2e.is_active else 'no'}")
    user = db.query(User).filter(User.email.ilike(email)).one_or_none() if email else None
    if user:
        print(f"database_user_exists: yes")
        print(f"active: {'yes' if user.is_active else 'no'}")
    else:
        any_admin = db.query(User).filter(User.is_admin == True).first()
        if any_admin:
            print(f"database_user_exists: yes (different email: {any_admin.email})")
            print(f"active: {'yes' if any_admin.is_active else 'no'}")
        else:
            print("database_user_exists: no")
            print("active: no")
finally:
    db.close()
'@

Invoke-AarohanComposeExec -InputScript $py -Args @("-T", "-e", "ADMIN_EMAIL=$($env:ADMIN_EMAIL)", "api", "python", "-")
