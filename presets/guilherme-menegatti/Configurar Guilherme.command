#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Job Apply Assistant — Configurar perfil Guilherme ==="
echo ""

python3 "$SCRIPT_DIR/install_preset.py"

if [[ -x "/Applications/JobApplyAssistant.app/Contents/Resources/playwright/driver/node" ]]; then
  NODE_BIN="/Applications/JobApplyAssistant.app/Contents/Resources/playwright/driver/node"
  CLI_JS="/Applications/JobApplyAssistant.app/Contents/Resources/playwright/driver/package/cli.js"
  if [[ -f "$CLI_JS" ]]; then
    echo ""
    echo "Instalando runtime WebKit no app (Safari engine)..."
    sudo env PLAYWRIGHT_BROWSERS_PATH=0 "$NODE_BIN" "$CLI_JS" install webkit || true
  fi
fi

echo ""
echo "Pronto. Abra o app e faça login no LinkedIn uma vez."
read -r -p "Pressione Enter para fechar..."
