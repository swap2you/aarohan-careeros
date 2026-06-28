#Requires -Version 5.1
<#
.SYNOPSIS
  Reset or create the local Docker admin user (development only).

.DESCRIPTION
  Updates the Career OS postgres admin via the API container using bcrypt (app.services.auth).
  Password is never stored in this script — pass -PasswordSecure, set RESET_LOCAL_ADMIN_PASSWORD
  for the current process, or enter at prompt.

.EXAMPLE
  Read-Host -AsSecureString when prompted, or set env RESET_LOCAL_ADMIN_PASSWORD for this session only.
  powershell -File scripts/local/Reset-LocalAdmin.ps1 -Force
#>
param(
    [string]$Email = "swapnilpatil.tech@gmail.com",
    [SecureString]$PasswordSecure,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

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

if (-not $PasswordSecure) {
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

$apiStatus = docker compose ps api --format "{{.Status}}" 2>$null
if (-not $apiStatus -or $apiStatus -notmatch "Up") {
    throw "API container is not running. Start stack first: docker compose up -d"
}

$py = @'
import os
import sys

from app.database import SessionLocal
from app.models import User
from app.services.auth import hash_password
from app.services.career_vault import sync_evidence_registry
from app.services.setup import mark_setup_complete

email = os.environ["LOCAL_ADMIN_RESET_EMAIL"]
password = os.environ["LOCAL_ADMIN_RESET_PASSWORD"]

if len(password) < 12:
    print("ERROR: password too short", file=sys.stderr)
    sys.exit(1)

db = SessionLocal()
try:
    for user in db.query(User).all():
        if user.email.lower() != email.lower():
            db.delete(user)
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
    $py | docker compose exec -T -e LOCAL_ADMIN_RESET_EMAIL -e LOCAL_ADMIN_RESET_PASSWORD api python -
    if ($LASTEXITCODE -ne 0) { throw "Admin reset failed (exit $LASTEXITCODE)." }
} finally {
    $env:LOCAL_ADMIN_RESET_EMAIL = $prevEmail
    $env:LOCAL_ADMIN_RESET_PASSWORD = $null
    if ($env:RESET_LOCAL_ADMIN_PASSWORD) { Remove-Item Env:RESET_LOCAL_ADMIN_PASSWORD -ErrorAction SilentlyContinue }
}

Write-Host "Login: POST http://localhost:8000/api/auth/login"
Write-Host "Email: $Email"
Write-Host "Then sign in at http://localhost:3000 before opening Settings."
