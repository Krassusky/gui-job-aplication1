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
1. Copy the whole `presets/guilherme-menegatti` folder to his Mac
   (or send him the setup zip you build from repo root).
2. From repo root on Mac, run:

   chmod +x scripts/setup_guilherme_preset_mac.command
   ./scripts/setup_guilherme_preset_mac.command

3. Open JobApply Assistant.
4. One-time only: Settings -> Platform Login -> Open LinkedIn login
   (use email/password, not Google sign-in).
5. Dashboard -> Start bot.

Important
---------
- LinkedIn session cannot be pre-installed (security). He must log in once.
- API key is in secrets.env (local only, not for public git).
- Rotate the Groq key after sharing/testing.
