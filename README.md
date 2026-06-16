# JobApply Assistant

A customized fork of [AutoApply](https://github.com/AbhishekMandapmalvi/AutoApply) for a **human-in-the-loop** LinkedIn job workflow:

**Find matching jobs → queue by score → pre-fill Easy Apply → your friend reviews and submits.**

## What changed from upstream AutoApply

| Setting | Upstream default | This fork |
|---------|------------------|-----------|
| Apply mode | `full_auto` | **`review`** (approve each application) |
| Max applications/day | 50 | **15** |
| Platforms | LinkedIn + Indeed | **LinkedIn only** |
| Delay between applies | 45s | **60s** |

No Docker required. Everything runs locally on Windows.

**Download (latest release):** https://github.com/Krassusky/gui-job-aplication1/releases/latest

---

## For your friend (end user)

### Download from GitHub

1. Open **https://github.com/Krassusky/gui-job-aplication1/releases/latest**
2. Download **`JobApplyAssistant-X.Y.Z-win-x64.zip`** (Assets section)
3. Extract the zip to a folder (e.g. `C:\JobApplyAssistant`)
4. Run **`JobApplyAssistant.exe`**
5. Install **Google Chrome** if prompted
6. If Windows SmartScreen warns → **More info → Run anyway**

See also **`LEIA-ME.txt`** inside the zip (Portuguese quick start).

### Daily use

1. Follow the setup wizard — upload CV, set job titles and locations
2. Use the **Guia** tab for step-by-step help
3. Log into LinkedIn once inside the app
4. Click **Start** — matching jobs appear in the queue
5. For each job: review the cover letter → **Approve & Apply** or **Skip**

### Updates

- **In the app:** Configurações → Atualizações → **Atualizar agora** (banner appears when a new version exists)
- **Manual:** download the new zip from GitHub Releases and replace the folder

Data is stored at `C:\Users\<name>\.autoapply\` and is kept across updates.

---

## For you (developer setup)

### Prerequisites

- Python 3.11+
- Google Chrome (Playwright uses Chromium)

Node.js is **not** required — upstream migrated from Electron to PyWebView + PyInstaller.

### Install and run (dev mode)

```powershell
cd c:\repositories-02\gui-job-aplication
py -m venv venv
.\venv\Scripts\activate
py setup_env.py
playwright install chromium
py run.py --gui
```

Or in PowerShell: `.\start.bat` (or double-click `start.bat` in File Explorer)

### Run tests

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_settings.py -v
```

### Build Windows executable for your friend

```powershell
.\venv\Scripts\pip install pyinstaller
.\venv\Scripts\pyinstaller autoapply.spec
```

Output: `dist\JobApplyAssistant\JobApplyAssistant.exe` — zip that folder and send it to him.

**Note:** Windows SmartScreen may warn on unsigned builds → **More info → Run anyway**.

---

## Publishing updates (for you)

Your friend can update from **Configurações → Atualizações** inside the app.

### Release a new version

1. Bump the version in `pyproject.toml` (e.g. `1.0.0` → `1.0.1`)
2. Commit and push to GitHub
3. Create and push a tag (must start with `v`):

```powershell
git tag v1.0.1
git push origin v1.0.1
```

4. GitHub Actions builds `JobApplyAssistant-x.y.z-win-x64.zip` and publishes it on **Releases**
5. Your friend gets a banner in the app, or downloads from **https://github.com/Krassusky/gui-job-aplication1/releases/latest**

Data in `C:\Users\<name>\.autoapply\` is kept across updates.

### Publish checklist

Before tagging `v1.0.0` (or next version):

- [ ] Version bumped in `pyproject.toml`
- [ ] All changes committed and pushed to `master`
- [ ] Tests pass: `pytest tests/ -q`
- [ ] Tag matches version: `git tag v1.0.0 && git push origin v1.0.0`
- [ ] Wait for **Actions → Release** workflow to finish
- [ ] Confirm zip appears under **GitHub → Releases → Assets**

---

## GitHub repo

**Fork:** https://github.com/Krassusky/gui-job-aplication1  
**Remote:** `git@github.com:Krassusky/gui-job-aplication1.git`  
**Branch:** `master`

Customizations are committed locally. Push once SSH is configured:

```powershell
git push -u origin master
```

### Fix SSH push (one-time)

If you see `Permission denied (publickey)`, add your SSH key to GitHub:

1. Copy your public key:

```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | Set-Clipboard
```

2. Open https://github.com/settings/keys → **New SSH key** → paste → save
3. Test and push:

```powershell
ssh -T git@github.com
git push -u origin master
```

### Pull upstream AutoApply updates later

```powershell
git fetch upstream
git merge upstream/master
```

---

## Developer setup

```
Desktop window (PyWebView)
    └── Flask dashboard (localhost)
            └── Playwright (visible Chrome)
                    └── LinkedIn Easy Apply (review mode pauses before submit)
```

---

## Risk reminder

LinkedIn prohibits automation in their Terms of Service. This fork defaults to **review mode** and a **15/day cap** to reduce risk. Your friend should not switch to full-auto or run at high volume.

## License

MIT (inherited from AutoApply upstream).
