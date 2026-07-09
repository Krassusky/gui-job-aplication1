#!/usr/bin/env python3
"""Install Guilherme Menegatti preset into ~/.autoapply/."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

PRESET_DIR = Path(__file__).resolve().parent
DATA_DIR = Path.home() / ".autoapply"
SECRETS_FILE = PRESET_DIR / "secrets.env"
CONFIG_TEMPLATE = PRESET_DIR / "config.template.json"


def _load_api_key() -> str:
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip()
    env_key = os.environ.get("GROQ_API_KEY", "").strip()
    if env_key:
        return env_key
    raise SystemExit(
        "Missing Groq API key. Create secrets.env with GROQ_API_KEY=... "
        f"or set GROQ_API_KEY before running.\nExpected: {SECRETS_FILE}"
    )


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def main() -> int:
    api_key = _load_api_key()
    if not CONFIG_TEMPLATE.exists():
        raise SystemExit(f"Missing template: {CONFIG_TEMPLATE}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "profile" / "jobs").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "profile" / "resumes").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "profile" / "cover_letters").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "profile" / "job_descriptions").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "backups").mkdir(parents=True, exist_ok=True)

    experiences_src = PRESET_DIR / "profile" / "experiences"
    experiences_dest = DATA_DIR / "profile" / "experiences"
    _copy_tree(experiences_src, experiences_dest)

    resume_src = PRESET_DIR / "default_resume.docx"
    if not resume_src.exists():
        raise SystemExit(f"Missing resume file: {resume_src}")
    resume_dest = DATA_DIR / "default_resume.docx"
    shutil.copy2(resume_src, resume_dest)

    raw = CONFIG_TEMPLATE.read_text(encoding="utf-8")
    raw = raw.replace("__AUTOAPPLY_DIR__", str(DATA_DIR).replace("\\", "/"))
    raw = raw.replace("__GROQ_API_KEY__", api_key)
    config_data = json.loads(raw)

    config_path = DATA_DIR / "config.json"
    config_path.write_text(
        json.dumps(config_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Preset installed successfully.")
    print(f"  Data dir: {DATA_DIR}")
    profile = config_data["profile"]
    llm = config_data["llm"]
    print(f"  Profile:  {profile['first_name']} {profile['last_name']}")
    print(f"  Email:    {profile['email']}")
    print(f"  LinkedIn: {profile['linkedin_url']}")
    print(f"  LLM:      {llm['provider']} ({llm['model']})")
    print(f"  Resume:   {resume_dest}")
    print("")
    print("Next steps for Guilherme:")
    print("  1) Open JobApply Assistant")
    print("  2) Settings -> Platform Login -> LinkedIn (one-time login in app browser)")
    print("  3) Dashboard -> start bot (review mode is enabled by default)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
