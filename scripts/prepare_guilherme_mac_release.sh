#!/usr/bin/env bash
# Prepare a Guilherme Mac release: bundle preset + API key into the app.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PRESET_DIR="$ROOT/presets/guilherme-menegatti"
SECRETS="$PRESET_DIR/secrets.env"

if [[ ! -f "$SECRETS" ]]; then
  echo "ERROR: Missing $SECRETS" >&2
  echo "Create it with: GROQ_API_KEY=gsk_..." >&2
  exit 1
fi

if ! grep -q '^GROQ_API_KEY=.' "$SECRETS"; then
  echo "ERROR: $SECRETS must contain GROQ_API_KEY=..." >&2
  exit 1
fi

echo "guilherme-menegatti" >"$ROOT/presets/.active_preset"
echo "Prepared Guilherme preset bundle marker."
echo "Next: pyinstaller autoapply.spec  (or push tag to trigger macOS release with secrets)"
