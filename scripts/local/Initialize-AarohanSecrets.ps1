#Requires -Version 5.1
<#
.SYNOPSIS
  Bootstrap local PowerShell SecretStore for Aarohan CareerOS.
.DESCRIPTION
  Stores secret names only in repo; values live in encrypted local vault.
#>
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

function Ensure-SecretModule {
    if (-not (Get-Module -ListAvailable -Name Microsoft.PowerShell.SecretManagement)) {
        Install-Module Microsoft.PowerShell.SecretManagement -Scope CurrentUser -Force -AllowClobber
    }
    if (-not (Get-Module -ListAvailable -Name Microsoft.PowerShell.SecretStore)) {
        Install-Module Microsoft.PowerShell.SecretStore -Scope CurrentUser -Force -AllowClobber
    }
    Import-Module Microsoft.PowerShell.SecretManagement
    Import-Module Microsoft.PowerShell.SecretStore
    if (-not (Get-SecretVault -Name AarohanLocal -ErrorAction SilentlyContinue)) {
        Register-SecretVault -Name AarohanLocal -ModuleName Microsoft.PowerShell.SecretStore -DefaultVault
        Set-SecretStoreConfiguration -Authentication Password -PasswordTimeout 900 -Interaction Prompt 900
    }
    Set-SecretVault -Name AarohanLocal -AsDefaultVault
}

function Set-SecretIfMissing {
    param([string]$Name, [string]$Prompt, [switch]$Required)
    $existing = Get-Secret -Name $Name -AsPlainText -ErrorAction SilentlyContinue
    if ($existing -and -not $Force) {
        Write-Host "[skip] $Name already set"
        return
    }
    if ($Required) {
        $secure = Read-Host -Prompt $Prompt -AsSecureString
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        )
        if ([string]::IsNullOrWhiteSpace($plain)) { throw "Required secret '$Name' was empty." }
        Set-Secret -Name $Name -Secret $plain -Vault AarohanLocal
        Write-Host "[ok] $Name stored"
    } else {
        $plain = Read-Host -Prompt "$Prompt (optional, Enter to skip)"
        if (-not [string]::IsNullOrWhiteSpace($plain)) {
            Set-Secret -Name $Name -Secret $plain -Vault AarohanLocal
            Write-Host "[ok] $Name stored"
        } else {
            Write-Host "[skip] $Name not provided"
        }
    }
}

Write-Host "Aarohan CareerOS — Initialize Local Secrets"
Ensure-SecretModule

Set-SecretIfMissing -Name APP_SECRET -Prompt "APP_SECRET (random 32+ chars)" -Required
Set-SecretIfMissing -Name POSTGRES_PASSWORD -Prompt "POSTGRES_PASSWORD" -Required
Set-SecretIfMissing -Name TOKEN_ENCRYPTION_KEY -Prompt "TOKEN_ENCRYPTION_KEY (Fernet key or random 32+ chars)" -Required
Set-SecretIfMissing -Name ADMIN_EMAIL -Prompt "Administrator email" -Required
Set-SecretIfMissing -Name ADMIN_PASSWORD -Prompt "Administrator password" -Required
Set-SecretIfMissing -Name GOOGLE_CLIENT_ID -Prompt "Google OAuth Client ID"
Set-SecretIfMissing -Name GOOGLE_CLIENT_SECRET -Prompt "Google OAuth Client Secret"
Set-SecretIfMissing -Name GOOGLE_OAUTH_REDIRECT_URI -Prompt "Google OAuth Redirect URI (default http://localhost:8000/api/integrations/google/callback)"
Set-SecretIfMissing -Name CAREER_GMAIL_ADDRESS -Prompt "Dedicated career Gmail address"
Set-SecretIfMissing -Name AI_API_KEY -Prompt "AI API key"
Set-SecretIfMissing -Name N8N_ENCRYPTION_KEY -Prompt "N8N encryption key"

Write-Host ""
Write-Host "Secret inventory configured in vault 'AarohanLocal'."
Write-Host "Next: pwsh .\scripts\local\Start-Aarohan.ps1"
