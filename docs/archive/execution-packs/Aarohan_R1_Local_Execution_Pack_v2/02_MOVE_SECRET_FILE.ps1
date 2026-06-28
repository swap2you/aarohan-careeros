$ErrorActionPreference = "Stop"

$RepoRoot = "C:\Development\Workspace\aarohan-careeros"
$Current = Join-Path $RepoRoot "AarohanSecrets\google-oauth-client.json"
$TargetDir = "C:\AarohanSecrets"
$Target = Join-Path $TargetDir "google-oauth-client.json"

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

if (Test-Path $Current) {
    Copy-Item $Current $Target -Force
    Write-Host "OAuth JSON copied to $Target"
} elseif (Test-Path $Target) {
    Write-Host "OAuth JSON already exists at $Target"
} else {
    throw "OAuth JSON was not found at either $Current or $Target"
}

$GitIgnore = Join-Path $RepoRoot ".gitignore"
$Required = @(
    "AarohanSecrets/",
    "private/",
    ".env.local",
    ".env.*.local"
)

$content = if (Test-Path $GitIgnore) { Get-Content $GitIgnore -Raw } else { "" }
foreach ($entry in $Required) {
    if ($content -notmatch [regex]::Escape($entry)) {
        Add-Content -Path $GitIgnore -Value "`n$entry"
    }
}

Write-Host "Verified gitignore entries."
Write-Host "After confirming the application reads $Target, delete the repository copy under AarohanSecrets."
