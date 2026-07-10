# Expose Job Hunter sync via Cloudflare Tunnel (`jobs.krassusky.com`)

Your Job Hunter runs on the **Windows PC** (port `8765`).  
Cloudflare Tunnel already runs on **Ubuntu**. Guilherme’s Mac will use:

```text
https://jobs.krassusky.com
```

```
Mac (Guilherme)
    → Cloudflare
        → Ubuntu cloudflared
            → localhost:8765  (SSH reverse tunnel from Windows)
                → Windows Job Hunter :8765
```

---

## 1. Keep the Job Hunter running on Windows

```powershell
powershell -File C:\repositories-02\gui-job-aplication\scripts\start_job_hunter.ps1
```

Confirm locally:

```powershell
curl http://127.0.0.1:8765/api/sync/health
```

---

## 2. Forward Windows `:8765` to Ubuntu (SSH reverse tunnel)

On the **Windows PC** (PowerShell), replace `user` with your Ubuntu SSH user:

```powershell
ssh -N -R 127.0.0.1:8765:127.0.0.1:8765 user@krassusky.com
```

Leave that window open (or run it as a scheduled task / autossh later).

On **Ubuntu**, verify the tunnel landed:

```bash
curl -s http://127.0.0.1:8765/api/sync/health
# {"status":"ok"}
```

> If SSH says “remote port forwarding failed”, enable this on Ubuntu `/etc/ssh/sshd_config`:
> `GatewayPorts no` is fine when binding `127.0.0.1` only.
> Also ensure nothing else is already using Ubuntu port 8765.

---

## 3. Add hostname in Cloudflare Zero Trust

1. Open [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels**
2. Open the tunnel that already serves `krassusky.com` on Ubuntu
3. **Public Hostname** → **Add**:

| Field | Value |
|--------|--------|
| Subdomain | `jobs` |
| Domain | `krassusky.com` |
| Type | `HTTP` |
| URL | `localhost:8765` |

4. Save. Cloudflare creates DNS for `jobs.krassusky.com` automatically.

### Optional: only allow `/api/sync/` (recommended)

In the public hostname, you can leave the full origin and rely on the sync **Bearer token**.  
Do **not** share the dashboard URL publicly (`/dashboard` has no auth today).

If your tunnel config is a YAML file on Ubuntu instead of the dashboard, add:

```yaml
ingress:
  - hostname: jobs.krassusky.com
    service: http://127.0.0.1:8765
  # ... your existing hostnames ...
  - service: http_status:404
```

Then restart:

```bash
sudo systemctl restart cloudflared
# or whatever unit name you use
```

---

## 4. Test from anywhere

```bash
curl -s https://jobs.krassusky.com/api/sync/health
```

Expected:

```json
{"status":"ok"}
```

With token (list jobs):

```bash
curl -s -H "Authorization: Bearer YOUR_SYNC_TOKEN" \
  https://jobs.krassusky.com/api/sync/jobs
```

---

## What Guilherme enters in the Mac app

**Settings → Import Jobs from Home Server**

| Field | Value |
|--------|--------|
| Sync server URL | `https://jobs.krassusky.com` |
| Sync token | from `SYNC-TOKEN-FOR-GUILHERME.txt` on the Windows PC |

Then: **Test connection** → **Import pending jobs**.

### Current production setup (Krassusky)

Already configured:

1. Dedicated Cloudflare tunnel `job-hunter` on Ubuntu (`cloudflared-jobs.service` user unit)
2. DNS: `jobs.krassusky.com` → that tunnel
3. SSH reverse tunnel from Windows hunter → Ubuntu `127.0.0.1:8765`
4. Health check: `curl -s https://jobs.krassusky.com/api/sync/health` → `{"status":"ok"}`

Restart tunnel on Windows after reboot:

```powershell
powershell -File C:\repositories-02\gui-job-aplication\scripts\tunnel_hunter_to_ubuntu.ps1
```

---

## Alternative: cloudflared on Windows (no SSH tunnel)

If you prefer not to use SSH:

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) on Windows
2. Authenticate and create/use a tunnel
3. Public hostname `jobs.krassusky.com` → `http://localhost:8765` on the **Windows** connector

Same Mac URL: `https://jobs.krassusky.com`

---

## Checklist

- [ ] Job Hunter running on Windows (`:8765`)
- [ ] SSH reverse tunnel Windows → Ubuntu **or** cloudflared on Windows
- [ ] Cloudflare public hostname `jobs.krassusky.com` → `localhost:8765`
- [ ] `curl https://jobs.krassusky.com/api/sync/health` returns ok
- [ ] Guilherme uses HTTPS URL + sync token
