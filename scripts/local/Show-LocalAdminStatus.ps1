#Requires -Version 5.1
<#
.SYNOPSIS
  Show local admin configuration status without printing passwords.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Import-LocalSecrets.ps1")

try {
    Import-AarohanSecrets -Mode LocalFile -LocalPath "C:\AarohanSecrets\aarohan.local.env"
} catch {
    Write-Host "configured_email: (secrets file missing or incomplete)"
    Write-Host "password_configured: no"
    Write-Host "database_user_exists: unknown (start API container)"
    Write-Host "active: unknown"
    exit 1
}

$email = $env:ADMIN_EMAIL
$passwordConfigured = if ([string]::IsNullOrWhiteSpace($env:ADMIN_PASSWORD)) { "no" } else { "yes" }
Write-Host "configured_email: $email"
Write-Host "password_configured: $passwordConfigured"

$apiStatus = docker compose ps api --format "{{.Status}}" 2>$null
if (-not $apiStatus -or $apiStatus -notmatch "Up") {
    Write-Host "database_user_exists: unknown (API not running)"
    Write-Host "active: unknown"
    exit 0
}

$py = @'
import os
from app.database import SessionLocal
from app.models import User

email = os.environ.get("ADMIN_EMAIL", "").lower()
db = SessionLocal()
try:
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

$py | docker compose exec -T -e ADMIN_EMAIL api python -
