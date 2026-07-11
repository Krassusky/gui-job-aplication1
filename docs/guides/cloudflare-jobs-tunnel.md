# Expose Job Hunter sync via Cloudflare Tunnel (`jobs.krassusky.com`)

The **Job Hunter runs on the Ubuntu iMac** (port `8765`).  
Cloudflare Tunnel on Ubuntu points `jobs.krassusky.com` → `http://127.0.0.1:8765`.  
Guilherme’s Mac imports jobs from:

```text
https://jobs.krassusky.com
```

```
Mac (Guilherme)
    → Cloudflare
        → Ubuntu cloudflared
            → localhost:8765
                → Ubuntu Job Hunter :8765
```

No Windows SSH reverse tunnel is required.

---

## 1. Run Job Hunter on Ubuntu

```bash
cd ~/gui-job-aplication   # or your clone path
cp -n .env.example .env   # fill LINKEDIN_* and AUTOAPPLY_SYNC_TOKEN
chmod +x scripts/start_job_hunter.sh
./scripts/start_job_hunter.sh
```

Or as a user systemd service:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/job-hunter.service ~/.config/systemd/user/
# Edit WorkingDirectory / ExecStart paths if the repo is not ~/gui-job-aplication
systemctl --user daemon-reload
systemctl --user enable --now job-hunter
```

Confirm locally:

```bash
curl -s http://127.0.0.1:8765/api/sync/health
# {"status":"ok","run_state":"...","sensors":{...}}
```

Dashboard (Start / Stop search + temps):

- LAN: `http://127.0.0.1:8765/dashboard`
- Public: `https://jobs.krassusky.com/dashboard` (paste sync token in the token field to Start/Stop)

Thermal pause uses the same `lm-sensors` readings as [dash.krassusky.com](https://dash.krassusky.com) / Immich migrator (CPU package, SMC, fan).

---

## 2. Cloudflare hostname (already configured)

Tunnel ingress should include:

```yaml
ingress:
  - hostname: jobs.krassusky.com
    service: http://127.0.0.1:8765
  - service: http_status:404
```

If you previously forwarded Windows → Ubuntu over SSH, **stop that tunnel** so only the local Ubuntu hunter owns port 8765.

---

## 3. Mac client (Guilherme)

1. Settings → Import Jobs from Home Server  
2. URL: `https://jobs.krassusky.com`  
3. Token: same as `AUTOAPPLY_SYNC_TOKEN` on Ubuntu  
4. Test connection → Import pending jobs  

---

## 4. Security notes

- Sync job list/detail/ack require `Authorization: Bearer <token>`
- Dashboard Start/Stop also require that token when configured
- Prefer Cloudflare Access on `jobs.krassusky.com` if you expose the dashboard publicly
- Do not commit `.env` (LinkedIn password + sync token)
