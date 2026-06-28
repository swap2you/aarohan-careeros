$Root = "C:\Development\Workspace\aarohan-careeros"
New-Item -ItemType Directory -Force -Path $Root | Out-Null
Set-Location $Root
git init
Write-Host "Repository initialized at $Root"
Write-Host "Extract the Aarohan V3 build kit into this folder, open it in Cursor, and run the START_HERE instruction."
