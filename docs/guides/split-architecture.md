# Split Architecture: Job Hunter + Mac Client

AutoApply can run as a **standalone desktop app** (unchanged) or as a **split deployment**:

| Role | Machine | Responsibility |
|------|---------|----------------|
| **Job Hunter** | Ubuntu home server (iMac) | 24/7 search, score, filter; thermal pause; sync API + Start/Stop dashboard |
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
# Foreground (loads .env, starts sync + hunt)
./scripts/start_job_hunter.sh

# Dashboard only until you click Start
./scripts/start_job_hunter.sh --stopped

# Single cycle (testing)
python -m worker.job_hunter --once
```

Dashboard: `http://127.0.0.1:8765/dashboard` — **Start search** / **Stop search**, live temps, pending Mac sync.

Thermal: hunting auto-pauses when CPU/SMC/fan exceed Immich thresholds (`HUNTER_HOT_*` in `.env`) and resumes when cool.

### Hunter dashboard (local browser)

While the hunter is running, open:

- `http://127.0.0.1:8765/dashboard` on the hunter machine
- `http://<lan-or-tailscale-ip>:8765/dashboard` from another device on the same network
- Public: `https://jobs.krassusky.com/dashboard` (requires login)

**Auth:** When `AUTOAPPLY_SYNC_TOKEN` or hunter password is set, the UI requires sign-in
(username/password or the sync token). Start/Stop and shared settings are not open publicly.

The page auto-refreshes every 5 seconds and shows:

- Cycle stats (found / filtered / saved)
- Jobs waiting for Mac sync (`pending_sync`)
- Live activity feed (found, filtered, saved, errors)
- **Shared settings** tab: edit profile / search / bot filters → `~/.autoapply/config.json`

JSON API: `GET /api/hunter/dashboard` (session or Bearer auth when configured)

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
5. Click **Pull shared profile & search** to copy profile + search filters from the hunter into local `~/.autoapply/config.json` (LLM keys and local resume paths are kept).

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
| GET | `/api/sync/config` | Shared profile + search_criteria + bot filters |
| PUT | `/api/sync/config` | Update shared subset on hunter `~/.autoapply/config.json` |

Hunter web UI (session cookie after login, or Bearer token):

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/hunter/session` | Auth status |
| POST | `/api/hunter/login` | `{username, password}` → session cookie |
| POST | `/api/hunter/logout` | Clear session |
| GET/PUT | `/api/hunter/config` | Same shared config as `/api/sync/config` |
| POST | `/api/hunter/start` / `stop` | Control hunt (requires login or Bearer) |

Dashboard login credentials (do not commit):

```bash
export AUTOAPPLY_HUNTER_USER=admin
# Preferred:
export AUTOAPPLY_HUNTER_PASSWORD_HASH="$(python -c 'from werkzeug.security import generate_password_hash; print(generate_password_hash("YOUR_PASSWORD"))')"
# Or plaintext: AUTOAPPLY_HUNTER_PASSWORD=...
# Or file: ~/.autoapply/hunter_auth.json → {"username","password_hash"}
```

Mac app endpoints (local):

| Method | Path | Description |
|--------|------|-------------|
| GET/PUT | `/api/sync/settings` | Read/update sync URL + token |
| POST | `/api/sync/test` | Test hunter connectivity |
| POST | `/api/sync/import` | Pull and import pending jobs |
| POST | `/api/sync/pull-config` | Pull shared profile/search into local config |

## 6. Phase 2 (not in this MVP)

- Resume generation on hunter before sync (Ollama/cloud with fallback)
- Friend's home PC as additional AI node
- Bidirectional sync (application status back to hunter)
- mTLS or Tailscale Serve instead of shared token
- Dedicated sync-only process vs embedded thread

## Backward compatibility

The desktop app works **unchanged** as a single machine. Split mode is opt-in via the Job Hunter worker and Mac sync settings.
