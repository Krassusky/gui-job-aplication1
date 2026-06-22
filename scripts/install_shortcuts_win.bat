@echo off
setlocal
cd /d "%~dp0"

set "EXE=%~dp0JobApplyAssistant.exe"
if not exist "%EXE%" (
  echo Could not find JobApplyAssistant.exe in this folder.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_shortcuts_win.ps1" -ExePath "%EXE%" -WorkDir "%~dp0"
if errorlevel 1 (
  echo Failed to create shortcuts.
  pause
  exit /b 1
)

echo.
echo Desktop and Start Menu shortcuts created successfully.
echo You can now launch Job Apply Assistant from your Desktop or Start Menu.
pause
