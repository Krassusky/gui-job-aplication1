param(
    [Parameter(Mandatory = $true)][string]$ExePath,
    [Parameter(Mandatory = $true)][string]$WorkDir
)

$ErrorActionPreference = "Stop"
$displayName = "Job Apply Assistant"
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shell = New-Object -ComObject WScript.Shell

function New-Shortcut($path) {
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $ExePath
    $shortcut.WorkingDirectory = $WorkDir
    $shortcut.IconLocation = "$ExePath,0"
    $shortcut.Save()
}

New-Shortcut (Join-Path $desktop "$displayName.lnk")
New-Shortcut (Join-Path $startMenu "$displayName.lnk")
