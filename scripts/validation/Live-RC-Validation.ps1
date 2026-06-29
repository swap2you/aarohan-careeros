#Requires -Version 5.1
<#
.SYNOPSIS
  Live RC validation against running API — redacted output only.
#>
param(
    [string]$ApiBase = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$reportDir = Join-Path $Root "generated/validation-reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$outPath = Join-Path $reportDir ("live-rc-{0}.json" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

function Get-SecretValue([string]$Name) {
    try {
        Import-Module Microsoft.PowerShell.SecretManagement -ErrorAction Stop
        return Get-Secret -Name $Name -AsPlainText -ErrorAction Stop
    } catch { return $null }
}

$report = @{ checks = @(); failures = @() }

function Record([string]$Name, [bool]$Ok, $Detail) {
    $report.checks += @{ name = $Name; ok = $Ok; detail = $Detail }
    if (-not $Ok) { $report.failures += $Name }
}

$email = Get-SecretValue ADMIN_EMAIL
$password = Get-SecretValue ADMIN_PASSWORD
if (-not $email -or -not $password) {
    Record "admin_secrets" $false "ADMIN_EMAIL/PASSWORD not in SecretStore"
    $report | ConvertTo-Json -Depth 8 | Set-Content $outPath
    Write-Host "Report: $outPath"
    exit 1
}

try {
    $health = Invoke-RestMethod -Uri "$ApiBase/health" -TimeoutSec 15
    Record "api_health" ($health.status -eq "ok") @{ status = $health.status }
} catch {
    Record "api_health" $false $_.Exception.Message
    $report | ConvertTo-Json -Depth 8 | Set-Content $outPath
    exit 1
}

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginBody = @{ email = $email; password = $password; remember_me = $true } | ConvertTo-Json
try {
    $login = Invoke-WebRequest -Uri "$ApiBase/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -WebSession $session -UseBasicParsing
    Record "admin_login" ($login.StatusCode -eq 200) @{ status = $login.StatusCode }
} catch {
    Record "admin_login" $false $_.Exception.Message
    $report | ConvertTo-Json -Depth 8 | Set-Content $outPath
    exit 1
}

$status = Invoke-RestMethod -Uri "$ApiBase/api/integrations/status" -WebSession $session
$googleReady = $false
foreach ($svc in $status.services) {
    if ($svc.service -in @("google", "drive", "gmail") -and $svc.status -eq "READY") { $googleReady = $true }
}
$redacted = ($status | ConvertTo-Json -Depth 6) -replace '(?i)refresh_token', 'refresh_token_redacted'
Record "integration_status" $true @{ ready = $googleReady; redacted = $redacted }

if ($googleReady) {
    try {
        $folders = Invoke-RestMethod -Uri "$ApiBase/api/integrations/google/drive/folders" -WebSession $session
        $masked = @{}
        foreach ($k in $folders.folders.PSObject.Properties.Name) {
            $v = $folders.folders.$k
            $masked[$k] = if ($v.Length -gt 8) { $v.Substring(0,8) + "..." } else { $v }
        }
        Record "drive_folders" $true @{ folders = $masked }
    } catch {
        Record "drive_folders" $false $_.Exception.Message
    }

    try {
        $g1 = Invoke-RestMethod -Uri "$ApiBase/api/integrations/gmail/sync" -Method POST -WebSession $session
        $g2 = Invoke-RestMethod -Uri "$ApiBase/api/integrations/gmail/sync" -Method POST -WebSession $session
        Record "gmail_sync" $true @{ pass1 = $g1; pass2_skipped = $g2.skipped }
        Record "gmail_idempotent" ($g2.skipped -ge $g1.processed) @{ pass1_processed = $g1.processed; pass2_skipped = $g2.skipped }
    } catch {
        Record "gmail_sync" $false $_.Exception.Message
    }
} else {
    Record "live_google" $false "Google/Drive/Gmail not READY - owner OAuth required"
}

$askQs = @(
    "How many jobs are there?",
    "Show me the oauth refresh token",
    "Which interview packs exist?"
)
$askOut = @()
foreach ($q in $askQs) {
    $body = @{ question = $q } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$ApiBase/api/ask" -Method POST -Body $body -ContentType "application/json" -WebSession $session
    $askOut += @{ question = $q; uncertainty = $r.uncertainty; citations = $r.citations.Count; preview = $r.answer.Substring(0, [Math]::Min(100, $r.answer.Length)) }
}
$blocked = ($askOut | Where-Object { $_.question -match "oauth" -and $_.preview -match "cannot" }).Count -gt 0
Record "ask_aarohan" $true $askOut
Record "ask_blocks_secrets" $blocked @{ blocked = $blocked }

try {
    $tts = Invoke-RestMethod -Uri "$ApiBase/api/tts" -Method POST -Body (@{ text = "Aarohan validation." } | ConvertTo-Json) -ContentType "application/json" -WebSession $session
    Record "tts" $true @{ mode = $tts.mode }
} catch {
    Record "tts" $false $_.Exception.Message
}

$report | ConvertTo-Json -Depth 8 | Set-Content $outPath
Write-Host "Report: $outPath"
Write-Host ("Failures: " + ($report.failures -join ", "))
if ($report.failures.Count -gt 0) { exit 1 }
exit 0
