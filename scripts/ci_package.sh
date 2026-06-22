#!/usr/bin/env bash
# Package PyInstaller output for GitHub Releases (Windows / macOS / Linux).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/dist"

VERSION="$(python -c "import tomllib; print(tomllib.load(open('../pyproject.toml','rb'))['project']['version'])")"

sign_windows_binary() {
  local binary="$1"
  if [[ -z "${WINDOWS_CERTIFICATE_BASE64:-}" || -z "${WINDOWS_CERTIFICATE_PASSWORD:-}" ]]; then
    return 0
  fi
  echo "Signing Windows binary..."
  local cert_path
  cert_path="$(mktemp -t jobapply-cert.XXXXXX.pfx)"
  echo "$WINDOWS_CERTIFICATE_BASE64" | base64 -d >"$cert_path"
  signtool sign /fd SHA256 /f "$cert_path" /p "$WINDOWS_CERTIFICATE_PASSWORD" /tr http://timestamp.digicert.com /td SHA256 "$binary"
  rm -f "$cert_path"
}

sign_macos_bundle() {
  local target="$1"
  if [[ -z "${APPLE_SIGNING_IDENTITY:-}" ]]; then
    return 0
  fi
  echo "Signing macOS bundle..."
  codesign --deep --force --options runtime --timestamp \
    --sign "$APPLE_SIGNING_IDENTITY" "$target"
  codesign --verify --deep --strict "$target"
}

notarize_macos_zip() {
  local zip_path="$1"
  if [[ -z "${APPLE_ID:-}" || -z "${APPLE_APP_SPECIFIC_PASSWORD:-}" || -z "${APPLE_TEAM_ID:-}" ]]; then
    return 0
  fi
  echo "Submitting macOS build for notarization..."
  xcrun notarytool submit "$zip_path" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_APP_SPECIFIC_PASSWORD" \
    --team-id "$APPLE_TEAM_ID" \
    --wait
}

if [[ "${RUNNER_OS:-}" == "Windows" || "$(uname -s 2>/dev/null || echo Windows)" == *MINGW* ]]; then
  PLATFORM="win-x64"
  cp ../LEIA-ME.txt JobApplyAssistant/LEIA-ME.txt
  cp ../scripts/install_shortcuts_win.bat "JobApplyAssistant/Install JobApply Assistant.bat"
  cp ../scripts/install_shortcuts_win.ps1 JobApplyAssistant/install_shortcuts_win.ps1
  sign_windows_binary "JobApplyAssistant/JobApplyAssistant.exe"
  7z a "JobApplyAssistant-${VERSION}-${PLATFORM}.zip" JobApplyAssistant/

elif [[ "${RUNNER_OS:-}" == "macOS" || "$(uname -s)" == "Darwin" ]]; then
  ARCH="$(uname -m)"
  if [[ "$ARCH" == "arm64" ]]; then
    PLATFORM="mac-arm64"
  else
    PLATFORM="mac-x64"
  fi
  cp ../scripts/install_shortcuts_mac.command "Install JobApply Assistant.command"
  chmod +x "Install JobApply Assistant.command"
  mkdir -p JobApplyAssistant.app/Contents/Resources
  cp ../LEIA-ME-MAC.txt JobApplyAssistant.app/Contents/Resources/LEIA-ME-MAC.txt
  chmod +x JobApplyAssistant.app/Contents/MacOS/JobApplyAssistant
  sign_macos_bundle "JobApplyAssistant.app"
  ditto -c -k --keepParent "JobApplyAssistant.app" "JobApplyAssistant-${VERSION}-${PLATFORM}.zip"
  # Add install helper alongside the app in the zip root
  zip "JobApplyAssistant-${VERSION}-${PLATFORM}.zip" "Install JobApply Assistant.command"
  notarize_macos_zip "JobApplyAssistant-${VERSION}-${PLATFORM}.zip"

else
  PLATFORM="linux-x64"
  cp ../LEIA-ME.txt JobApplyAssistant/LEIA-ME.txt
  chmod +x JobApplyAssistant/JobApplyAssistant
  zip -r "JobApplyAssistant-${VERSION}-${PLATFORM}.zip" JobApplyAssistant/
fi

echo "Created JobApplyAssistant-${VERSION}-${PLATFORM}.zip"
