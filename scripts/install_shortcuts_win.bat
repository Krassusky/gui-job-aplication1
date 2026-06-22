@echo off
setlocal
cd /d "%~dp0"

echo Desbloqueando arquivos baixados da internet...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-ChildItem -LiteralPath '%~dp0' -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue"

set "EXE=%~dp0JobApplyAssistant.exe"
if not exist "%EXE%" (
  echo Nao foi possivel encontrar JobApplyAssistant.exe nesta pasta.
  pause
  exit /b 1
)

echo Criando atalhos na Area de Trabalho e no Menu Iniciar...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_shortcuts_win.ps1" -ExePath "%EXE%" -WorkDir "%~dp0"
if errorlevel 1 (
  echo Falha ao criar atalhos.
  echo.
  echo Tente manualmente:
  echo 1. Clique com o botao direito em "Install JobApply Assistant.bat"
  echo 2. Propriedades - marque "Desbloquear" - OK
  echo 3. Execute este arquivo novamente
  pause
  exit /b 1
)

echo.
echo Atalhos criados com sucesso.
echo Agora abra "Job Apply Assistant" na Area de Trabalho ou Menu Iniciar.
pause
