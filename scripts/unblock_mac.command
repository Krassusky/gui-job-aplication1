#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="JobApplyAssistant.app"
APP_PATH="$SCRIPT_DIR/$APP_NAME"

echo "Removendo bloqueio de segurança do download (quarentena)..."
if [[ -d "$APP_PATH" ]]; then
  xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true
fi
xattr -dr com.apple.quarantine "$SCRIPT_DIR" 2>/dev/null || true

echo ""
echo "Pronto. Agora você pode:"
echo "  1. Dar duplo clique em Install JobApply Assistant.command"
echo "  ou"
echo "  2. Abrir JobApplyAssistant.app diretamente"
echo ""
read -r -p "Pressione Enter para fechar..."
