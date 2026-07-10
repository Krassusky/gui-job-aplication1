# Keep an SSH reverse tunnel open: Windows Job Hunter → Ubuntu (for Cloudflare)
# Usage:
#   powershell -File scripts\tunnel_hunter_to_ubuntu.ps1

$ErrorActionPreference = "Stop"
$Target = if ($env:AUTOAPPLY_SSH_TARGET) { $env:AUTOAPPLY_SSH_TARGET } else { "server.krassusky.com" }

Write-Host "Forwarding local 8765 to $Target remote 127.0.0.1:8765"
Write-Host "Keep this window open. Cloudflare jobs.krassusky.com uses Ubuntu localhost:8765."
Write-Host "Test on Ubuntu: curl -s http://127.0.0.1:8765/api/sync/health"
Write-Host ""

ssh -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
  -o ExitOnForwardFailure=yes `
  -R 127.0.0.1:8765:127.0.0.1:8765 $Target
