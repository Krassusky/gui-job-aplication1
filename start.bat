@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo First-time setup required. Run: py setup_env.py
  pause
  exit /b 1
)
venv\Scripts\python.exe run.py --gui
