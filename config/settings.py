"""Application configuration and settings models.

Implements: FR-001 (data directory), FR-003 (configuration model),
            NFR-QW1 (keyring integration).
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyring helpers — lazy-checked, graceful fallback to plaintext
# ---------------------------------------------------------------------------

_keyring_available: bool | None = None  # lazy-init sentinel
KEYRING_SERVICE = "autoapply"
KEYRING_KEY_NAME = "llm_api_key"


def _keyring_key_name(provider_id: str | None = None) -> str:
    if provider_id:
        return f"{KEYRING_KEY_NAME}_{provider_id}"
    return KEYRING_KEY_NAME


def _check_keyring() -> bool:
    """Return True if the OS keyring backend is usable. Result is cached."""
    global _keyring_available
    if _keyring_available is not None:
        return _keyring_available
    try:
        import keyring
        keyring.get_password(KEYRING_SERVICE, "__probe__")
        _keyring_available = True
    except Exception:
        _logger.warning("keyring unavailable — API key stored in plaintext config")
        _keyring_available = False
    return _keyring_available


class UserProfile(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone_country_code: str = "+1"
    phone: str
    address_line1: str = ""
    address_line2: str = ""
    city: str
    state: str
    zip_code: str = ""
    country: str = "United States"
    bio: str
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    fallback_resume_path: str | None = None
    screening_answers: dict = {}
    spoken_languages: list[dict[str, str]] = [
        {"code": "pt", "level": "native"},
        {"code": "en", "level": "fluent"},
        {"code": "es", "level": "fluent"},
    ]

    # Backward-compatible property — used by AI engine prompts and Lever/Indeed
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    # Backward-compatible property — formatted location string
    @property
    def location(self) -> str:
        parts = [self.city, self.state]
        loc = ", ".join(p for p in parts if p)
        if self.country and self.country != "United States":
            loc = f"{loc}, {self.country}" if loc else self.country
        return loc

    # Full phone with country code
    @property
    def phone_full(self) -> str:
        if self.phone_country_code and not self.phone.startswith("+"):
            return f"{self.phone_country_code}{self.phone}"
        return self.phone

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data):
        """Accept old config format with full_name and location strings."""
        if isinstance(data, dict):
            # Migrate full_name → first_name + last_name
            if "full_name" in data and "first_name" not in data:
                parts = data.pop("full_name", "").split(None, 1)
                data["first_name"] = parts[0] if parts else ""
                data["last_name"] = parts[1] if len(parts) > 1 else ""
            # Migrate location → city + state
            if "location" in data and "city" not in data:
                loc = data.pop("location", "")
                parts = [p.strip() for p in loc.split(",")]
                data["city"] = parts[0] if parts else ""
                data["state"] = parts[1] if len(parts) > 1 else ""
                if len(parts) > 2:
                    data["country"] = parts[2]
        return data


class SearchCriteria(BaseModel):
    job_titles: list[str]
    locations: list[str]
    remote_only: bool = False
    salary_min: int | None = None
    keywords_include: list[str] = []
    keywords_exclude: list[str] = []
    experience_levels: list[str] = ["mid", "senior"]
    job_languages: list[str] = ["pt", "en", "es"]


class ScheduleConfig(BaseModel):
    enabled: bool = False
    days_of_week: list[str] = ["mon", "tue", "wed", "thu", "fri"]
    start_time: str = "09:00"  # HH:MM in 24-hour local time
    end_time: str = "17:00"    # HH:MM in 24-hour local time


class LLMProviderEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    provider: str = ""  # "anthropic" | "openai" | "google" | "deepseek"
    api_key: str = ""
    model: str = ""  # Empty = use default for provider


class LLMConfig(BaseModel):
    provider: str = ""  # Active provider (legacy + convenience mirror)
    api_key: str = ""
    model: str = ""
    providers: list[LLMProviderEntry] = Field(default_factory=list)
    active_id: str = ""
    ollama_fallback_enabled: bool = False
    ollama_model: str = ""

    @model_validator(mode="after")
    def _normalize_providers(self) -> "LLMConfig":
        if not self.providers and self.provider:
            entry_id = self.active_id or str(uuid.uuid4())
            self.providers = [
                LLMProviderEntry(
                    id=entry_id,
                    label=self._default_label(self.provider),
                    provider=self.provider,
                    api_key=self.api_key,
                    model=self.model,
                )
            ]
            self.active_id = entry_id
        elif self.providers and not self.active_id:
            self.active_id = self.providers[0].id
        self._sync_legacy_from_active()
        return self

    @staticmethod
    def _default_label(provider: str) -> str:
        labels = {
            "anthropic": "Anthropic",
            "openai": "OpenAI",
            "google": "Google Gemini",
            "deepseek": "DeepSeek",
            "groq": "Groq",
            "openrouter": "OpenRouter",
            "ollama": "Ollama (local)",
        }
        return labels.get(provider, provider.title() or "AI Provider")

    def get_active_entry(self) -> LLMProviderEntry | None:
        if not self.providers:
            if self.provider:
                return LLMProviderEntry(
                    id=self.active_id or "legacy",
                    label=self._default_label(self.provider),
                    provider=self.provider,
                    api_key=self.api_key,
                    model=self.model,
                )
            return None
        for entry in self.providers:
            if entry.id == self.active_id:
                return entry
        return self.providers[0]

    def _sync_legacy_from_active(self) -> None:
        active = self.get_active_entry()
        if not active:
            return
        self.provider = active.provider
        self.api_key = active.api_key
        self.model = active.model
        self.active_id = active.id

    def sync_active_entry_from_legacy(self) -> None:
        """Update the active provider entry from legacy top-level fields."""
        if not self.providers:
            return
        for entry in self.providers:
            if entry.id == self.active_id:
                entry.provider = self.provider
                entry.api_key = self.api_key
                entry.model = self.model
                if not entry.label:
                    entry.label = self._default_label(entry.provider)
                return


class ResumeReuseConfig(BaseModel):
    """Configuration for smart resume reuse via Knowledge Base assembly."""
    enabled: bool = True
    min_score: float = 0.0
    min_experience_bullets: int = 6
    scoring_method: str = "auto"  # "tfidf" | "onnx" | "auto"
    cover_letter_strategy: str = "generate"  # "generate" | "template"


class LatexConfig(BaseModel):
    """Configuration for LaTeX resume compilation."""
    template: str = "classic"  # template name in templates/latex/
    font_family: str = "helvetica"  # helvetica, times, palatino
    font_size: int = 11  # 10, 11, 12
    margin: str = "0.75in"


class BotConfig(BaseModel):
    enabled_platforms: list[str] = ["linkedin"]
    min_match_score: int = 75
    max_applications_per_day: int = 15
    delay_between_applications_seconds: int = 60
    search_interval_seconds: int = 1800
    apply_mode: str = "review"  # "full_auto" | "review" | "watch"
    watch_mode: bool = False  # Deprecated: use apply_mode instead
    cover_letter_enabled: bool = True
    cover_letter_template: str = ""
    schedule: ScheduleConfig = ScheduleConfig()


class SyncConfig(BaseModel):
    """Settings for importing jobs from a remote Job Hunter server."""
    sync_server_url: str = ""
    sync_token: str = ""


class AppConfig(BaseModel):
    profile: UserProfile
    search_criteria: SearchCriteria
    bot: BotConfig = BotConfig()
    llm: LLMConfig = LLMConfig()
    resume_reuse: ResumeReuseConfig = ResumeReuseConfig()
    latex: LatexConfig = LatexConfig()
    sync: SyncConfig = SyncConfig()
    company_blacklist: list[str] = []
    version: str = "2.0"


def get_data_dir() -> Path:
    return Path.home() / ".autoapply"


def _hydrate_llm_keys_from_keyring(llm: LLMConfig) -> None:
    if not _check_keyring():
        return

    import keyring

    legacy_key = keyring.get_password(KEYRING_SERVICE, _keyring_key_name())
    if legacy_key and not llm.api_key:
        llm.api_key = legacy_key

    for entry in llm.providers:
        if entry.api_key:
            continue
        stored = keyring.get_password(KEYRING_SERVICE, _keyring_key_name(entry.id))
        if stored:
            entry.api_key = stored

    llm._sync_legacy_from_active()


def _migrate_legacy_key_to_keyring(llm: LLMConfig) -> bool:
    if not _check_keyring() or not llm.api_key:
        return False

    import keyring

    active = llm.get_active_entry()
    key_name = _keyring_key_name(active.id if active else None)
    if keyring.get_password(KEYRING_SERVICE, key_name):
        return False

    keyring.set_password(KEYRING_SERVICE, key_name, llm.api_key)
    if key_name != _keyring_key_name():
        keyring.set_password(KEYRING_SERVICE, _keyring_key_name(), llm.api_key)
    return True


def _store_llm_keys_in_keyring(llm: LLMConfig) -> None:
    if not _check_keyring():
        return

    import keyring

    for entry in llm.providers:
        if entry.api_key:
            keyring.set_password(
                KEYRING_SERVICE, _keyring_key_name(entry.id), entry.api_key
            )
    if llm.api_key:
        keyring.set_password(KEYRING_SERVICE, _keyring_key_name(), llm.api_key)


def load_config() -> AppConfig | None:
    config_path = get_data_dir() / "config.json"
    if not config_path.exists():
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    config = AppConfig(**data)

    _hydrate_llm_keys_from_keyring(config.llm)

    if _migrate_legacy_key_to_keyring(config.llm):
        _save_config_raw(config, strip_api_key=_check_keyring())
        _logger.info("Migrated API key from config.json to OS keyring")

    config.llm._sync_legacy_from_active()
    return config


def save_config(config: AppConfig) -> None:
    config.llm.sync_active_entry_from_legacy()
    config.llm._sync_legacy_from_active()
    _store_llm_keys_in_keyring(config.llm)
    _save_config_raw(config, strip_api_key=_check_keyring())


def _strip_llm_api_keys(dump: dict[str, Any]) -> None:
    llm = dump.get("llm", {})
    llm["api_key"] = ""
    for entry in llm.get("providers", []):
        entry["api_key"] = ""


def _save_config_raw(config: AppConfig, strip_api_key: bool = False) -> None:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = data_dir / "config.json"
    dump = config.model_dump()
    if strip_api_key:
        _strip_llm_api_keys(dump)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=2)


def is_first_run() -> bool:
    return not (get_data_dir() / "config.json").exists()
