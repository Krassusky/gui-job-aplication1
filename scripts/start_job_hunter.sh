#!/usr/bin/env bash
# Start Job Hunter on Ubuntu (sync API + dashboard; hunt starts via dashboard or auto).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

: "${AUTOAPPLY_SYNC_HOST:=127.0.0.1}"
: "${AUTOAPPLY_SYNC_PORT:=8765}"
: "${AUTOAPPLY_OLLAMA_FALLBACK:=1}"

export AUTOAPPLY_SYNC_HOST AUTOAPPLY_SYNC_PORT AUTOAPPLY_OLLAMA_FALLBACK

if [[ -z "${AUTOAPPLY_SYNC_TOKEN:-}" ]]; then
  TOKEN_FILE="${HOME}/.autoapply/.sync_token"
  if [[ -f "$TOKEN_FILE" ]]; then
    export AUTOAPPLY_SYNC_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
  else
    mkdir -p "${HOME}/.autoapply"
    AUTOAPPLY_SYNC_TOKEN="$(openssl rand -hex 32)"
    echo "$AUTOAPPLY_SYNC_TOKEN" > "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
    export AUTOAPPLY_SYNC_TOKEN
    echo "Generated sync token → $TOKEN_FILE (give this to Guilherme)"
  fi
fi

if [[ ! -d "$ROOT/venv" ]]; then
  echo "Missing venv at $ROOT/venv — create with: python3 -m venv venv && ./venv/bin/pip install -e ."
  exit 1
fi

echo "Dashboard: http://127.0.0.1:${AUTOAPPLY_SYNC_PORT}/dashboard"
echo "Public (Cloudflare): https://jobs.krassusky.com/dashboard"
echo "Health: curl -s http://127.0.0.1:${AUTOAPPLY_SYNC_PORT}/api/sync/health"
echo "Starting Job Hunter (Ctrl+C to stop process)…"

# Default: start hunting immediately. Use --stopped to wait for dashboard Start.
exec "$ROOT/venv/bin/python" -m worker.job_hunter "$@"
