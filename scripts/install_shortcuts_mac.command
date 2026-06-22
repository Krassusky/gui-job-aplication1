#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="JobApplyAssistant.app"
APP_PATH="$SCRIPT_DIR/$APP_NAME"
DISPLAY_NAME="Job Apply Assistant"

if [[ ! -d "$APP_PATH" ]]; then
  echo "Could not find $APP_NAME next to this installer."
  exit 1
fi

DEST="/Applications/$APP_NAME"
if [[ "$APP_PATH" != "$DEST" ]]; then
  if [[ -d "$DEST" ]]; then
    rm -rf "$DEST"
  fi
  echo "Copying to Applications..."
  cp -R "$APP_PATH" "$DEST"
  APP_PATH="$DEST"
fi

DESKTOP="$HOME/Desktop"
echo "Creating Desktop shortcut..."
osascript -e "tell application \"Finder\" to make alias file at POSIX file \"$DESKTOP\" to POSIX file \"$APP_PATH\""

echo ""
echo "Done. Job Apply Assistant is in Applications and on your Desktop."
