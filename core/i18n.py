"""Internationalization support for backend response strings (LE-3).

Loads translation strings from JSON locale files in static/locales/.
Provides a `t(key, **params)` function for translating error/status messages.

Usage:
    from core.i18n import t, set_locale, get_locale

    t("errors.application_not_found")  # => "Application not found"
    t("errors.invalid_status", valid_statuses="a, b")  # => interpolation
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_strings: dict = {}
_en_strings: dict = {}
_locale: str = "pt"
_locales_dir: Path = Path(__file__).resolve().parent.parent / "static" / "locales"


def _load_locale(locale: str) -> dict[str, object]:
    """Load a locale JSON file and return the parsed dict."""
    path = _locales_dir / f"{locale}.json"
    if not path.exists():
        logger.warning("Locale file not found: %s", path)
        return {}
    try:
        result: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
        return result
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load locale %s: %s", locale, e)
        return {}


def set_locale(locale: str) -> None:
    """Switch the active locale. Falls back to 'en' if not found."""
    global _strings, _en_strings, _locale
    _en_strings = _load_locale("en")
    strings = _load_locale(locale)
    if strings:
        _strings = strings
        _locale = locale
    elif locale != "en":
        logger.warning("Locale '%s' not found, falling back to 'en'", locale)
        _strings = _en_strings
        _locale = "en"


def get_locale() -> str:
    """Return the current locale code."""
    return _locale


def get_available_locales() -> list[str]:
    """Return list of available locale codes."""
    if not _locales_dir.exists():
        return []
    return sorted(p.stem for p in _locales_dir.glob("*.json"))


def _lookup(key: str, strings: dict) -> str | None:
    parts = key.split(".")
    val: object = strings
    for part in parts:
        if isinstance(val, dict) and part in val:
            val = val[part]
        else:
            return None
    return val if isinstance(val, str) else None


def t(key: str, **params: object) -> str:
    """Translate a dot-notation key, with optional {placeholder} interpolation.

    Falls back to English, then to the key itself if the translation is not found.

    Args:
        key: Dot-separated key, e.g. "errors.application_not_found".
        **params: Values for {placeholder} interpolation.

    Returns:
        Translated string, or the key if not found.
    """
    translated = _lookup(key, _strings)
    if translated is None and _locale != "en":
        translated = _lookup(key, _en_strings)
    if translated is None:
        return key
    if not params:
        return translated
    return re.sub(
        r"\{(\w+)\}",
        lambda m: str(params[m.group(1)]) if m.group(1) in params else m.group(0),
        translated,
    )


# Auto-load Portuguese (pt-BR content in pt.json) on import
set_locale("pt")
