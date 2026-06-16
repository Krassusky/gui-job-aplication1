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
python -m venv venv
.\venv\Scripts\activate
python setup_env.py
playwright install chromium
python run.py --gui
```

A desktop window opens with the dashboard.

### Run tests

```powershell
python -m pytest tests/test_settings.py -v
```

### Build Windows executable for your friend

```powershell
.\venv\Scripts\activate
pip install pyinstaller
pyinstaller autoapply.spec
```

Output: `dist\AutoApply\AutoApply.exe` — zip that folder and send it to him, or rename to `JobApplyAssistant.exe`.

**Note:** Windows SmartScreen may warn on unsigned builds → **More info → Run anyway**.

---

## Create your GitHub fork

The GitHub CLI (`gh`) is not installed on this machine, so the fork must be created on GitHub:

1. Go to https://github.com/AbhishekMandapmalvi/AutoApply
2. Click **Fork** → create under your account
3. Then connect this local repo:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/gui-job-aplication.git
git add -A
git commit -m "Fork AutoApply with review-mode defaults for LinkedIn assistant"
git push -u origin main
```

To pull upstream updates later:

```powershell
git remote add upstream https://github.com/AbhishekMandapmalvi/AutoApply.git
git fetch upstream
git merge upstream/master
```

---

## Architecture

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
