#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PRESET_DIR="$SCRIPT_DIR/presets/guilherme-menegatti"
APP_BIN="/Applications/JobApplyAssistant.app/Contents/MacOS/JobApplyAssistant"

echo "=== Job Apply Assistant — Configurar perfil Guilherme ==="
echo ""

if [[ ! -d "$PRESET_DIR" ]]; then
  echo "Erro: preset não encontrado em:"
  echo "  $PRESET_DIR"
  read -r -p "Pressione Enter para fechar..."
  exit 1
fi

if [[ -x "$APP_BIN" ]]; then
  PYTHON_BIN="$APP_BIN"
  echo "Usando Python embutido do app..."
else
  PYTHON_BIN="python3"
  echo "App não encontrado em /Applications — usando python3 do sistema..."
fi

export PYTHONPATH="$(cd "$SCRIPT_DIR" && pwd)"
"$PYTHON_BIN" "$PRESET_DIR/install_preset.py"

# Install WebKit runtime inside app bundle when available.
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
echo "Configuração concluída."
echo "Abra o app e faça login no LinkedIn uma vez em Login em Plataformas."
read -r -p "Pressione Enter para fechar..."
