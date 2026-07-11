"""Username/password auth for the Job Hunter web dashboard.

Credentials (never commit secrets):
  Env:
    AUTOAPPLY_HUNTER_USER          — default \"admin\"
    AUTOAPPLY_HUNTER_PASSWORD      — plaintext (hashed in memory for verify)
    AUTOAPPLY_HUNTER_PASSWORD_HASH — werkzeug hash (preferred over plaintext)
    AUTOAPPLY_HUNTER_SECRET        — Flask session secret (optional)
  File ~/.autoapply/hunter_auth.json:
    {\"username\": \"admin\", \"password_hash\": \"scrypt:...\"}

If no password is configured, dashboard/control stay open on localhost only;
remote clients must use Bearer AUTOAPPLY_SYNC_TOKEN or set hunter credentials.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from config.settings import get_data_dir

logger = logging.getLogger(__name__)

AUTH_FILE = "hunter_auth.json"
SECRET_FILE = ".hunter_secret"
SESSION_USER_KEY = "hunter_user"


def _auth_path() -> Path:
    return get_data_dir() / AUTH_FILE


def _secret_path() -> Path:
    return get_data_dir() / SECRET_FILE


def get_flask_secret() -> str:
    """Stable secret for signed session cookies."""
    env = os.environ.get("AUTOAPPLY_HUNTER_SECRET", "").strip()
    if env:
        return env
    sync = os.environ.get("AUTOAPPLY_SYNC_TOKEN", "").strip()
    if sync:
        return f"hunter-session:{sync}"
    path = _secret_path()
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    get_data_dir().mkdir(parents=True, exist_ok=True)
    value = secrets.token_hex(32)
    path.write_text(value, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return value


def _load_auth_file() -> dict:
    path = _auth_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read hunter auth file: %s", e)
        return {}


def credentials_configured() -> bool:
    """True when a password (hash or plaintext) is available."""
    if os.environ.get("AUTOAPPLY_HUNTER_PASSWORD_HASH", "").strip():
        return True
    if os.environ.get("AUTOAPPLY_HUNTER_PASSWORD", "").strip():
        return True
    data = _load_auth_file()
    return bool(data.get("password_hash") or data.get("password"))


def get_username() -> str:
    env = os.environ.get("AUTOAPPLY_HUNTER_USER", "").strip()
    if env:
        return env
    data = _load_auth_file()
    return str(data.get("username") or "admin")


def _password_hash() -> str | None:
    env_hash = os.environ.get("AUTOAPPLY_HUNTER_PASSWORD_HASH", "").strip()
    if env_hash:
        return env_hash
    data = _load_auth_file()
    if data.get("password_hash"):
        return str(data["password_hash"])
    # Plaintext fallbacks — verify via generate+check path
    return None


def _plaintext_password() -> str | None:
    env = os.environ.get("AUTOAPPLY_HUNTER_PASSWORD", "").strip()
    if env:
        return env
    data = _load_auth_file()
    pw = data.get("password")
    return str(pw) if pw else None


def verify_password(username: str, password: str) -> bool:
    if not username or not password:
        return False
    if username != get_username():
        return False
    stored_hash = _password_hash()
    if stored_hash:
        try:
            return check_password_hash(stored_hash, password)
        except Exception:
            return False
    plain = _plaintext_password()
    if plain is not None:
        return secrets.compare_digest(plain, password)
    return False


def save_password(username: str, password: str) -> Path:
    """Persist hashed credentials under ~/.autoapply/hunter_auth.json."""
    get_data_dir().mkdir(parents=True, exist_ok=True)
    path = _auth_path()
    payload = {
        "username": username.strip() or "admin",
        "password_hash": generate_password_hash(password),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def hash_password(password: str) -> str:
    return generate_password_hash(password)


# Shared config fields synced between hunter and Mac client (no LLM keys / local paths).
SHARED_PROFILE_KEYS = (
    "first_name",
    "last_name",
    "email",
    "phone_country_code",
    "phone",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "zip_code",
    "country",
    "bio",
    "linkedin_url",
    "portfolio_url",
    "screening_answers",
    "spoken_languages",
)

SHARED_BOT_KEYS = (
    "enabled_platforms",
    "min_match_score",
    "max_applications_per_day",
    "delay_between_applications_seconds",
    "search_interval_seconds",
    "cover_letter_enabled",
)


def extract_shared_config(config) -> dict:
    """Build the shared profile + search + bot subset for sync."""
    if config is None:
        return {"profile": {}, "search_criteria": {}, "bot": {}}
    profile = config.profile.model_dump()
    bot = config.bot.model_dump()
    return {
        "profile": {k: profile.get(k) for k in SHARED_PROFILE_KEYS},
        "search_criteria": config.search_criteria.model_dump(),
        "bot": {k: bot.get(k) for k in SHARED_BOT_KEYS},
    }


def merge_shared_config(config, payload: dict):
    """Apply shared subset onto an AppConfig in place; returns config."""
    from config.settings import BotConfig, SearchCriteria, UserProfile

    if not isinstance(payload, dict):
        return config

    if "profile" in payload and isinstance(payload["profile"], dict):
        current = config.profile.model_dump()
        for k in SHARED_PROFILE_KEYS:
            if k in payload["profile"]:
                current[k] = payload["profile"][k]
        config.profile = UserProfile(**current)

    if "search_criteria" in payload and isinstance(payload["search_criteria"], dict):
        current = config.search_criteria.model_dump()
        current.update(payload["search_criteria"])
        config.search_criteria = SearchCriteria(**current)

    if "bot" in payload and isinstance(payload["bot"], dict):
        current = config.bot.model_dump()
        for k in SHARED_BOT_KEYS:
            if k in payload["bot"]:
                current[k] = payload["bot"][k]
        config.bot = BotConfig(**current)

    return config
