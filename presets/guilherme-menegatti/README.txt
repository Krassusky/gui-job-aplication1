Job Apply Assistant — Preset Guilherme Menegatti
================================================

This folder pre-fills profile, CV, experience files, job search criteria,
and Groq API settings for Guilherme.

What is included
----------------
- Profile: name, email, phone, Mexico City, LinkedIn URL
- CV: default_resume.docx
- Experience files for AI resume generation
- Job titles: Transformation / Process Improvement / Knowledge Manager / etc.
- Bot: LinkedIn enabled, review mode, weekday schedule 09:00-18:00
- LLM: Groq (llama-3.3-70b-versatile)

Install on Guilherme's Mac
--------------------------
Option A — Guilherme Mac app build (recommended)
1. On the build machine, create presets/guilherme-menegatti/secrets.env:
     GROQ_API_KEY=gsk_...
2. Run: bash scripts/prepare_guilherme_mac_release.sh
3. Build Mac release (pyinstaller / GitHub release with GUILHERME_GROQ_API_KEY secret).
4. Guilherme installs the .zip — profile, resume, and Groq key apply on first open.
5. One-time only: Settings -> Platform Login -> LinkedIn
6. Settings -> Import Jobs from Home Server (home PC URL + token)

Option B — Manual preset (no special build)
1. Copy the whole `presets/guilherme-menegatti` folder to his Mac
   (or send him the setup zip you build from repo root).
2. Double-click Configurar Guilherme.command (or run setup script).
3. Open JobApply Assistant.
4. One-time only: Settings -> Platform Login -> LinkedIn
5. Settings -> Import Jobs from Home Server

Important
---------
- LinkedIn session cannot be pre-installed (security). He must log in once.
- API key is in secrets.env (local only, not for public git).
- Rotate the Groq key after sharing/testing.
