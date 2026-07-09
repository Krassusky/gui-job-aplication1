# Start Job Hunter + sync API on this PC (run in PowerShell, keep window open)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$tokenFile = Join-Path $env:USERPROFILE ".autoapply\SYNC-TOKEN-FOR-GUILHERME.txt"
if (-not (Test-Path $tokenFile)) {
    $token = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) })
    "AUTOAPPLY_SYNC_TOKEN=$token" | Set-Content $tokenFile -Encoding UTF8
} else {
    $token = (Get-Content $tokenFile -Raw).Trim() -replace '^AUTOAPPLY_SYNC_TOKEN=', ''
}

$env:AUTOAPPLY_SYNC_TOKEN = $token
$env:AUTOAPPLY_SYNC_HOST = "0.0.0.0"
$env:AUTOAPPLY_SYNC_PORT = "8765"
$env:AUTOAPPLY_OLLAMA_FALLBACK = "1"

Write-Host "Dashboard: http://192.168.15.3:8765/dashboard"
Write-Host "Sync API: http://192.168.15.3:8765 (use your LAN/Tailscale IP)"
Write-Host "Token saved in: $tokenFile"
Write-Host "Starting Job Hunter (Ctrl+C to stop)..."

& "$Root\venv\Scripts\python.exe" -m worker.job_hunter
