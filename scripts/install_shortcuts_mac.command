#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="JobApplyAssistant.app"
APP_PATH="$SCRIPT_DIR/$APP_NAME"

echo "=== Job Apply Assistant — Instalação (macOS) ==="
echo ""

if [[ ! -d "$APP_PATH" ]]; then
  echo "Erro: não encontrei $APP_NAME nesta pasta."
  echo "Extraia o .zip e execute este arquivo ao lado do $APP_NAME."
  read -r -p "Pressione Enter para fechar..."
  exit 1
fi

echo "[1/3] Removendo bloqueio de download (quarentena)..."
xattr -dr com.apple.quarantine "$SCRIPT_DIR" 2>/dev/null || true

DEST="/Applications/$APP_NAME"
if [[ "$APP_PATH" != "$DEST" ]]; then
  echo "[2/3] Copiando para Aplicativos..."
  if [[ -d "$DEST" ]]; then
    rm -rf "$DEST"
  fi
  cp -R "$APP_PATH" "$DEST"
  APP_PATH="$DEST"
  xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true
else
  echo "[2/3] O app já está em Aplicativos."
fi

echo "[3/3] Criando atalho na Área de Trabalho..."
DESKTOP="$HOME/Desktop"
osascript -e "tell application \"Finder\" to make alias file at POSIX file \"$DESKTOP\" to POSIX file \"$APP_PATH\"" \
  >/dev/null 2>&1 || true

echo ""
echo "Instalação concluída!"
echo "  • Aplicativos: $APP_PATH"
echo "  • Área de Trabalho: atalho criado"
echo ""
echo "Abra pelo Launchpad, Área de Trabalho ou pasta Aplicativos."
read -r -p "Pressione Enter para fechar..."
