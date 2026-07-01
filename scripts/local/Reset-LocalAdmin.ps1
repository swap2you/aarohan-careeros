#Requires -Version 5.1
<#
.SYNOPSIS
  Reset or create the local Docker admin user (development only).

.DESCRIPTION
  Updates the Career OS postgres admin via the API container using bcrypt (app.services.auth).
  Password is never stored in this script — pass -PasswordSecure, set RESET_LOCAL_ADMIN_PASSWORD
  for the current process, use -UseConfiguredPassword, or enter at prompt.

.EXAMPLE
  pwsh scripts/local/Reset-LocalAdmin.ps1 -Force -UseConfiguredPassword
#>
param(
    [string]$Email = "",
    [SecureString]$PasswordSecure,
    [switch]$Force,
    [switch]$UseConfiguredPassword
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot "Invoke-AarohanCompose.ps1")
Import-AarohanRepoEnvLocal -Root $Root

if ([string]::IsNullOrWhiteSpace($Email)) {
    $Email = $env:ADMIN_EMAIL
}
if ([string]::IsNullOrWhiteSpace($Email)) {
    throw "ADMIN_EMAIL is not configured in .env.local"
}

function Get-PlainPassword {
    param([SecureString]$Secure)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if (-not $Force) {
    $confirm = Read-Host "Reset local admin to '$Email'? Type RESET to continue"
    if ($confirm -ne "RESET") { throw "Cancelled." }
}

if ($UseConfiguredPassword) {
    if ([string]::IsNullOrWhiteSpace($env:ADMIN_PASSWORD)) {
        throw "ADMIN_PASSWORD is not configured in .env.local"
    }
    $PasswordSecure = ConvertTo-SecureString $env:ADMIN_PASSWORD -AsPlainText -Force
} elseif (-not $PasswordSecure) {
    if ($env:RESET_LOCAL_ADMIN_PASSWORD) {
        $PasswordSecure = ConvertTo-SecureString $env:RESET_LOCAL_ADMIN_PASSWORD -AsPlainText -Force
    } else {
        $PasswordSecure = Read-Host -AsSecureString "Enter new local admin password (min 12 characters)"
    }
}

$plainPassword = Get-PlainPassword -Secure $PasswordSecure
if ($plainPassword.Length -lt 12) {
    throw "Password must be at least 12 characters."
}

$apiStatus = docker compose --env-file (Join-Path $Root ".env.local") ps api --format "{{.Status}}" 2>$null
if (-not $apiStatus -or $apiStatus -notmatch "Up") {
    Write-Host "API container not running — starting stack..."
    Invoke-AarohanCompose up -d
    Start-Sleep -Seconds 5
}

$py = @'
import os
import sys

from app.database import SessionLocal
from app.models import User
from app.services.auth import hash_password
from app.services.career_vault import sync_evidence_registry
from app.services.local_auth import deactivate_stray_e2e_user
from app.services.setup import mark_setup_complete

email = os.environ["LOCAL_ADMIN_RESET_EMAIL"]
password = os.environ["LOCAL_ADMIN_RESET_PASSWORD"]

if len(password) < 12:
    print("ERROR: password too short", file=sys.stderr)
    sys.exit(1)

db = SessionLocal()
try:
    from app.models import UserSession

    deactivate_stray_e2e_user(db)
    for user in db.query(User).all():
        if user.email.lower() != email.lower():
            db.query(UserSession).filter(UserSession.user_id == user.id).delete()
            db.delete(user)
    db.flush()
    target = db.query(User).filter(User.email == email).one_or_none()
    hashed = hash_password(password)
    if target:
        target.hashed_password = hashed
        target.is_admin = True
        target.is_active = True
    else:
        db.add(User(email=email, hashed_password=hashed, is_admin=True, is_active=True))
    db.commit()
    mark_setup_complete(db)
    sync_evidence_registry(db)
    print(f"OK: local admin ready for {email}")
finally:
    db.close()
'@

$prevEmail = $env:LOCAL_ADMIN_RESET_EMAIL
$prevPassword = $env:LOCAL_ADMIN_RESET_PASSWORD
try {
    $env:LOCAL_ADMIN_RESET_EMAIL = $Email
    $env:LOCAL_ADMIN_RESET_PASSWORD = $plainPassword
    $plainPassword = $null
    Invoke-AarohanComposeExec -InputScript $py -Args @("-T", "-e", "LOCAL_ADMIN_RESET_EMAIL", "-e", "LOCAL_ADMIN_RESET_PASSWORD", "api", "python", "-")
} finally {
    $env:LOCAL_ADMIN_RESET_EMAIL = $prevEmail
    $env:LOCAL_ADMIN_RESET_PASSWORD = $null
    if ($env:RESET_LOCAL_ADMIN_PASSWORD) { Remove-Item Env:RESET_LOCAL_ADMIN_PASSWORD -ErrorAction SilentlyContinue }
}

Write-Host "Login: POST http://127.0.0.1:8000/api/auth/login"
Write-Host "Email: $Email"
Write-Host "Or use Enter Local Admin at http://127.0.0.1:3000/login when bypass is enabled."
