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

---

## For your friend (end user)

1. Install **JobApply Assistant** from the `.exe` you build (see below)
2. Run the setup wizard — upload CV, set job titles and locations
3. Log into LinkedIn once inside the app
4. Click **Start** — matching jobs appear in the queue
5. For each job: review the cover letter → **Approve & Apply** or **Skip**

Data is stored at `C:\Users\<name>\.autoapply\`.

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

Or double-click `start.bat` after setup.

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
