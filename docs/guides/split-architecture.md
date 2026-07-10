# Split Architecture: Job Hunter + Mac Client

AutoApply can run as a **standalone desktop app** (unchanged) or as a **split deployment**:

| Role | Machine | Responsibility |
|------|---------|----------------|
| **Job Hunter** | Ubuntu home server | 24/7 search, score, filter; save discoveries; optional sync API |
| **Mac Client** | Friend's Mac (Guilherme) | Import shared finds; review; apply via local browser |

A third node (friend's home PC with AI) can be added later without changing this design.

## Overview

```
┌─────────────────────┐         Tailscale / LAN          ┌─────────────────────┐
│  Ubuntu Job Hunter  │  GET /api/sync/jobs              │     Mac Client      │
│  - Playwright       │  GET /api/sync/jobs/{id}           │  - PyWebView UI     │
│  - Groq / cloud LLM │  POST /api/sync/jobs/{id}/ack    │  - Local browser    │
│  - Ollama fallback  │◄────────────────────────────────►│  - Review & apply   │
└─────────────────────┘                                  └─────────────────────┘
```

## 1. Ubuntu Job Hunter setup

### Prerequisites

- Python 3.11+ and project dependencies (`pip install -r requirements.txt`)
- Playwright browsers: `playwright install chromium`
- [Ollama](https://ollama.com/) installed and running: `ollama pull llama3.2`
- LinkedIn/Indeed sessions (log in once via the desktop app or copy `~/.autoapply/browser_profile`)

### Configure

Use the same `~/.autoapply/config.json` as the desktop app (job titles, locations, filters, LLM provider).

Recommended LLM settings on the hunter:

- Primary: **Groq** (or another cloud provider)
- Enable **Fall back to local Ollama** in Settings → AI Provider, **or** set:

```bash
export AUTOAPPLY_OLLAMA_FALLBACK=1
export AUTOAPPLY_OLLAMA_BASE_URL=http://127.0.0.1:11434
export AUTOAPPLY_OLLAMA_MODEL=llama3.2
```

### Sync API (share finds with Mac)

Generate a shared secret (do not commit this):

```bash
export AUTOAPPLY_SYNC_TOKEN="$(openssl rand -hex 32)"
```

Expose the API on your LAN/Tailscale IP (default bind is `127.0.0.1` only):

```bash
export AUTOAPPLY_SYNC_HOST=0.0.0.0
export AUTOAPPLY_SYNC_PORT=8765
```

### Run the hunter

```bash
# Foreground (sync API starts automatically in a background thread)
python -m worker.job_hunter

# Or via script
python scripts/run_job_hunter.py

# Single cycle (testing)
python -m worker.job_hunter --once

# Without embedded sync API (e.g. you run sync separately)
python -m worker.job_hunter --no-sync
```

The worker:

- Runs search → score → filter only (no apply, no review gate)
- Saves passing jobs as `pending_sync` in `~/.autoapply/autoapply.db`
- Waits `search_interval_seconds` between cycles (from config)
- Logs structured lines to stdout

### Hunter dashboard (local browser)

While the hunter is running, open:

- `http://127.0.0.1:8765/dashboard` on the hunter machine
- `http://<lan-or-tailscale-ip>:8765/dashboard` from another device on the same network

The page auto-refreshes every 10 seconds and shows:

- Cycle stats (found / filtered / saved)
- Jobs waiting for Mac sync (`pending_sync`)
- Live activity feed (found, filtered, saved, errors)

JSON API (no auth): `GET /api/hunter/dashboard`

### systemd example (optional)

```ini
[Unit]
Description=AutoApply Job Hunter
After=network.target ollama.service

[Service]
Type=simple
User=youruser
Environment=AUTOAPPLY_SYNC_TOKEN=your-shared-secret
Environment=AUTOAPPLY_SYNC_HOST=0.0.0.0
Environment=AUTOAPPLY_SYNC_PORT=8765
Environment=AUTOAPPLY_OLLAMA_FALLBACK=1
WorkingDirectory=/path/to/gui-job-aplication
ExecStart=/path/to/venv/bin/python -m worker.job_hunter
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## 2. Networking (pick one)

### Option A — Cloudflare Tunnel + domain (recommended for remote Mac)

See [cloudflare-jobs-tunnel.md](./cloudflare-jobs-tunnel.md).

Summary:

1. Job Hunter on Windows (`:8765`)
2. SSH reverse tunnel Windows → Ubuntu `localhost:8765` (or cloudflared on Windows)
3. Cloudflare public hostname `jobs.krassusky.com` → `http://localhost:8765`
4. Mac sync URL: `https://jobs.krassusky.com`

### Option B — Tailscale / LAN

1. Install [Tailscale](https://tailscale.com/) on hunter and Mac (same tailnet).
2. Note the hunter Tailscale IP (e.g. `100.x.x.x`).
3. From Mac, verify: `curl http://100.x.x.x:8765/api/sync/health`
4. Mac client sync URL: `http://100.x.x.x:8765`

Firewall: allow inbound TCP on port `8765` on the hunter (or use Tailscale ACLs).

## 3. Mac client setup (Guilherme)

1. Install and run AutoApply normally (`python run.py` or packaged app).
2. Open **Settings → Import Jobs from Home Server**.
3. Set:
   - **Sync server URL**: `https://jobs.krassusky.com` (Cloudflare) **or** `http://<tailscale-ip>:8765`
   - **Sync token**: same value as `AUTOAPPLY_SYNC_TOKEN` on the hunter
4. Click **Test connection**, then **Import pending jobs**.

Imported jobs appear in **Applications** with status `discovered` for review/apply. The Mac acks each job on the hunter so it is not re-imported.

Apply still uses the **local browser on the Mac** — no remote apply.

## 4. Ollama fallback behavior

When generating resumes/cover letters (desktop or future hunter AI phase):

1. Try the configured **cloud provider** (Groq, Anthropic, etc.).
2. On **401, 402, 429**, or network timeout, fall back to **local Ollama** if:
   - Settings → **Fall back to local Ollama** is enabled, or
   - `AUTOAPPLY_OLLAMA_FALLBACK=1` is set.
3. **Ollama** can also be selected as the primary provider (no API key).

Env vars:

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUTOAPPLY_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API base |
| `AUTOAPPLY_OLLAMA_MODEL` | `llama3.2` | Model when not set in config |
| `AUTOAPPLY_OLLAMA_FALLBACK` | off | Force fallback without UI toggle |

## 5. Sync API reference

Auth: `Authorization: Bearer <AUTOAPPLY_SYNC_TOKEN>`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sync/health` | Liveness (no auth) |
| GET | `/api/sync/jobs?since=<iso>` | List `pending_sync` jobs |
| GET | `/api/sync/jobs/{id}` | Job detail + description |
| POST | `/api/sync/jobs/{id}/ack` | Mark imported on client |

Mac app endpoints (local):

| Method | Path | Description |
|--------|------|-------------|
| GET/PUT | `/api/sync/settings` | Read/update sync URL + token |
| POST | `/api/sync/test` | Test hunter connectivity |
| POST | `/api/sync/import` | Pull and import pending jobs |

## 6. Phase 2 (not in this MVP)

- Resume generation on hunter before sync (Ollama/cloud with fallback)
- Friend's home PC as additional AI node
- Bidirectional sync (application status back to hunter)
- mTLS or Tailscale Serve instead of shared token
- Dedicated sync-only process vs embedded thread

## Backward compatibility

The desktop app works **unchanged** as a single machine. Split mode is opt-in via the Job Hunter worker and Mac sync settings.
