# Prepare Guilherme Mac release marker (run before pyinstaller on macOS CI or Mac).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Secrets = Join-Path $Root "presets\guilherme-menegatti\secrets.env"

if (-not (Test-Path $Secrets)) {
    Write-Error "Missing $Secrets — create with GROQ_API_KEY=gsk_..."
}
$content = Get-Content $Secrets -Raw
if ($content -notmatch 'GROQ_API_KEY=\S') {
    Write-Error "$Secrets must contain GROQ_API_KEY=..."
}

"guilherme-menegatti" | Set-Content (Join-Path $Root "presets\.active_preset") -Encoding UTF8
Write-Host "Prepared Guilherme preset bundle. Build Mac release next (tag push or pyinstaller on Mac)."
