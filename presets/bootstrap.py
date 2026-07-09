"""Install bundled user presets on first launch (Guilherme Mac edition)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from config.settings import AppConfig, get_data_dir, load_config, save_config

logger = logging.getLogger(__name__)

PRESET_VERSION = 1


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_active_bundled_preset_id() -> str | None:
    """Return preset id when this build was prepared with presets/.active_preset."""
    marker = _project_root() / "presets" / ".active_preset"
    if not marker.is_file():
        return None
    preset_id = marker.read_text(encoding="utf-8").strip()
    if not preset_id:
        return None
    preset_dir = _project_root() / "presets" / preset_id
    return preset_id if preset_dir.is_dir() else None


def _marker_path(preset_id: str) -> Path:
    return get_data_dir() / f".preset-{preset_id}-v{PRESET_VERSION}"


def _load_api_key(preset_dir: Path) -> str:
    secrets_file = preset_dir / "secrets.env"
    if secrets_file.exists():
        for line in secrets_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip()

    env_key = os.environ.get("GROQ_API_KEY", "").strip()
    if env_key:
        return env_key

    return ""


def _copy_tree(src: Path, dest: Path, *, overwrite: bool) -> None:
    if not src.exists():
        return
    if dest.exists() and overwrite:
        shutil.rmtree(dest)
    if not dest.exists():
        shutil.copytree(src, dest)


def _config_needs_preset(config: AppConfig | None, preset_email: str) -> bool:
    if config is None:
        return True
    email = (config.profile.email or "").strip().lower()
    if not email:
        return True
    if email == preset_email.lower():
        return not _has_api_key(config)
    return False


def _has_api_key(config: AppConfig) -> bool:
    if (config.llm.api_key or "").strip():
        return True
    return any((entry.api_key or "").strip() for entry in config.llm.providers)


def _load_template_config(preset_dir: Path, api_key: str) -> dict[str, Any]:
    template_path = preset_dir / "config.template.json"
    if not template_path.exists():
        raise FileNotFoundError(f"Missing preset template: {template_path}")

    data_dir = get_data_dir()
    raw = template_path.read_text(encoding="utf-8")
    raw = raw.replace("__AUTOAPPLY_DIR__", str(data_dir).replace("\\", "/"))
    raw = raw.replace("__GROQ_API_KEY__", api_key)
    return json.loads(raw)


def install_preset(
    preset_dir: Path,
    *,
    merge: bool = False,
    force: bool = False,
) -> bool:
    """Install preset files into ~/.autoapply. Returns True if changes were made."""
    preset_id = preset_dir.name
    data_dir = get_data_dir()
    template_data = _load_template_config(preset_dir, _load_api_key(preset_dir))
    preset_email = template_data.get("profile", {}).get("email", "")
    existing = load_config()

    marker = _marker_path(preset_id)
    if marker.exists() and not force and not merge:
        if existing and not _config_needs_preset(existing, preset_email):
            return False

    api_key = _load_api_key(preset_dir)
    if not api_key:
        logger.warning(
            "Preset %s: no Groq API key in bundle — profile/resume will install, "
            "add GROQ_API_KEY in Settings",
            preset_id,
        )

    data_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("profile/jobs", "profile/resumes", "profile/cover_letters",
                "profile/job_descriptions", "backups"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)

    experiences_src = preset_dir / "profile" / "experiences"
    experiences_dest = data_dir / "profile" / "experiences"
    overwrite_experiences = not experiences_dest.exists() or not any(experiences_dest.iterdir())
    _copy_tree(experiences_src, experiences_dest, overwrite=overwrite_experiences or force)

    resume_src = preset_dir / "default_resume.docx"
    resume_dest = data_dir / "default_resume.docx"
    if resume_src.exists() and (force or not resume_dest.exists()):
        shutil.copy2(resume_src, resume_dest)

    if existing and merge:
        current = existing.model_dump()
        for section, values in template_data.items():
            if section == "profile" and isinstance(values, dict):
                profile = current.setdefault("profile", {})
                for key, value in values.items():
                    if key == "fallback_resume_path":
                        profile[key] = str(resume_dest).replace("\\", "/")
                    elif not str(profile.get(key, "")).strip():
                        profile[key] = value
            elif section == "llm" and isinstance(values, dict):
                llm = current.setdefault("llm", {})
                if api_key and not _has_api_key(existing):
                    llm.update(values)
            elif section not in current or force:
                current[section] = values
        config = AppConfig(**current)
    else:
        template_data["profile"]["fallback_resume_path"] = str(resume_dest).replace("\\", "/")
        if api_key:
            template_data["llm"]["api_key"] = api_key
            for entry in template_data.get("llm", {}).get("providers", []):
                entry["api_key"] = api_key
        config = AppConfig(**template_data)

    save_config(config)
    marker.write_text(str(PRESET_VERSION), encoding="utf-8")

    profile = config.profile
    logger.info(
        "Installed preset %s for %s %s",
        preset_id,
        profile.first_name,
        profile.last_name,
    )
    return True


def _preset_email_from_template(preset_dir: Path) -> str:
    template_path = preset_dir / "config.template.json"
    raw = template_path.read_text(encoding="utf-8")
    raw = raw.replace("__AUTOAPPLY_DIR__", "/tmp/autoapply")
    raw = raw.replace("__GROQ_API_KEY__", "")
    return json.loads(raw).get("profile", {}).get("email", "")


def apply_bundled_preset_if_needed() -> bool:
    """Apply bundled preset on first launch or when profile/API key still empty."""
    preset_id = get_active_bundled_preset_id()
    if not preset_id:
        return False

    preset_dir = _project_root() / "presets" / preset_id
    template_path = preset_dir / "config.template.json"
    if not template_path.exists():
        logger.warning("Bundled preset %s is missing config.template.json", preset_id)
        return False

    preset_email = _preset_email_from_template(preset_dir)

    marker = _marker_path(preset_id)
    existing = load_config()
    needs_install = (
        not marker.exists()
        or _config_needs_preset(existing, preset_email)
    )
    if not needs_install:
        return False

    merge = existing is not None
    installed = install_preset(preset_dir, merge=merge)
    if installed:
        logger.info("Bundled preset %s applied (merge=%s)", preset_id, merge)
    return installed
