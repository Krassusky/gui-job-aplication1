@echo off
setlocal
cd /d "%~dp0"

echo Desbloqueando todos os arquivos desta pasta...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-ChildItem -LiteralPath '%~dp0' -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue"

echo.
echo Pronto. Agora execute JobApplyAssistant.exe
echo Se o Windows avisar sobre seguranca: "Mais informacoes" -^> "Executar assim mesmo"
pause
