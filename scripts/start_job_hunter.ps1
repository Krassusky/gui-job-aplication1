# Start Job Hunter + sync API on this PC (run in PowerShell, keep window open)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$tokenFile = Join-Path $env:USERPROFILE ".autoapply\SYNC-TOKEN-FOR-GUILHERME.txt"
if (-not (Test-Path $tokenFile)) {
    $token = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) })
    @(
        "AUTOAPPLY_SYNC_TOKEN=$token"
        ""
        "Give this token to Guilherme in Mac app Settings -> Import Jobs from Home Server"
    ) | Set-Content $tokenFile -Encoding UTF8
} else {
    $line = Get-Content $tokenFile | Where-Object { $_ -match '^AUTOAPPLY_SYNC_TOKEN=' } | Select-Object -First 1
    if (-not $line) {
        throw "No AUTOAPPLY_SYNC_TOKEN= line in $tokenFile"
    }
    $token = ($line -split '=', 2)[1].Trim()
}

$env:AUTOAPPLY_SYNC_TOKEN = $token
$env:AUTOAPPLY_SYNC_HOST = "0.0.0.0"
$env:AUTOAPPLY_SYNC_PORT = "8765"
$env:AUTOAPPLY_OLLAMA_FALLBACK = "1"

Write-Host "Dashboard: http://127.0.0.1:8765/dashboard"
Write-Host "Public sync URL (Guilherme): https://jobs.krassusky.com"
Write-Host "Token saved in: $tokenFile"
Write-Host "Starting Job Hunter (Ctrl+C to stop)..."
Write-Host "Also keep SSH tunnel open: powershell -File scripts\tunnel_hunter_to_ubuntu.ps1"

& "$Root\venv\Scripts\python.exe" -m worker.job_hunter
