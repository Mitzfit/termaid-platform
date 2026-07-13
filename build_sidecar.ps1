# Build the local backend sidecar (Windows 11) and place it for Tauri.
#   $env:TERMAID_ROOT="C:\path\to\termaid-complete-windows"; .\scripts\build_sidecar.ps1
$ErrorActionPreference = "Stop"
if (-not $env:TERMAID_ROOT) { throw "set TERMAID_ROOT to your extracted TermAId CLI project" }
Push-Location "$PSScriptRoot\..\backend"
pip install -r requirements.txt pyinstaller
pyinstaller termaid-backend.spec --noconfirm
python ..\scripts\name_sidecar.py
Pop-Location
Write-Host "Done. Now: cd desktop-mobile; npm run build"
