"""Language helpers for profile, search, resume, and applications."""

from __future__ import annotations

from typing import Any

LANGUAGE_META: dict[str, Any] = {
    "pt": {
        "name_en": "Portuguese",
        "name_pt": "Português",
        "name_es": "Portugués",
        "levels": {
            "native": {"en": "Native", "pt": "Nativo", "es": "Nativo"},
            "fluent": {"en": "Fluent", "pt": "Fluente", "es": "Fluido"},
            "intermediate": {"en": "Intermediate", "pt": "Intermediário", "es": "Intermedio"},
            "basic": {"en": "Basic", "pt": "Básico", "es": "Básico"},
        },
        "search_terms": ["português", "portuguese", "bilingual portuguese", "portugués"],
        "jd_terms": ["portuguese", "português", "portugues", "portugués", "bilingual"],
    },
    "en": {
        "name_en": "English",
        "name_pt": "Inglês",
        "name_es": "Inglés",
        "levels": {
            "native": {"en": "Native", "pt": "Nativo", "es": "Nativo"},
            "fluent": {"en": "Fluent", "pt": "Fluente", "es": "Fluido"},
            "intermediate": {"en": "Intermediate", "pt": "Intermediário", "es": "Intermedio"},
            "basic": {"en": "Basic", "pt": "Básico", "es": "Básico"},
        },
        "search_terms": ["english", "inglés", "ingles", "bilingual english"],
        "jd_terms": ["english", "inglés", "ingles", "bilingual", "fluent english"],
    },
    "es": {
        "name_en": "Spanish",
        "name_pt": "Espanhol",
        "name_es": "Español",
        "levels": {
            "native": {"en": "Native", "pt": "Nativo", "es": "Nativo"},
            "fluent": {"en": "Fluent", "pt": "Fluente", "es": "Fluido"},
            "intermediate": {"en": "Intermediate", "pt": "Intermediário", "es": "Intermedio"},
            "basic": {"en": "Basic", "pt": "Básico", "es": "Básico"},
        },
        "search_terms": ["español", "spanish", "espanol", "bilingual spanish"],
        "jd_terms": ["spanish", "español", "espanol", "bilingual", "fluent spanish"],
    },
}

DEFAULT_SPOKEN_LANGUAGES = [
    {"code": "pt", "level": "native"},
    {"code": "en", "level": "fluent"},
    {"code": "es", "level": "fluent"},
]

DEFAULT_JOB_LANGUAGES = ["pt", "en", "es"]


def language_display_name(code: str, locale: str = "en") -> str:
    meta = LANGUAGE_META.get(code, {})
    if locale.startswith("pt"):
        return str(meta.get("name_pt", code))
    if locale.startswith("es"):
        return str(meta.get("name_es", code))
    return str(meta.get("name_en", code))


def level_display_name(code: str, level: str, locale: str = "en") -> str:
    meta = LANGUAGE_META.get(code, {})
    levels: Any = meta.get("levels", {})
    if isinstance(levels, dict) and level in levels:
        level_map = levels[level]
        if isinstance(level_map, dict):
            if locale.startswith("pt"):
                return str(level_map.get("pt", level))
            if locale.startswith("es"):
                return str(level_map.get("es", level))
            return str(level_map.get("en", level))
    return level


def format_languages_line(
    spoken_languages: list[dict[str, str]] | None,
    locale: str = "en",
) -> str:
    """Format for resume header and screening forms."""
    if not spoken_languages:
        return ""
    parts = []
    for entry in spoken_languages:
        code = entry.get("code", "")
        level = entry.get("level", "fluent")
        if not code:
            continue
        name = language_display_name(code, locale)
        lvl = level_display_name(code, level, locale)
        parts.append(f"{name} ({lvl})")
    return ", ".join(parts)


def format_languages_resume_section(
    spoken_languages: list[dict[str, str]] | None,
    locale: str = "en",
) -> str:
    line = format_languages_line(spoken_languages, locale)
    if not line:
        return ""
    heading = "Languages" if locale.startswith("en") else ("Idiomas" if locale.startswith("es") else "Idiomas")
    return f"## {heading}\n{line}"


def jd_terms_for_languages(codes: list[str]) -> list[str]:
    terms: list[str] = []
    for code in codes:
        meta = LANGUAGE_META.get(code, {})
        jd = meta.get("jd_terms", [])
        if isinstance(jd, list):
            terms.extend(jd)
    return list(dict.fromkeys(terms))


def expand_search_titles(title: str, job_languages: list[str] | None) -> list[str]:
    """Extra LinkedIn keyword queries to surface multilingual roles."""
    if not job_languages:
        return [title]
    queries = [title]
    for code in job_languages:
        meta = LANGUAGE_META.get(code, {})
        search_terms = meta.get("search_terms", [])
        if isinstance(search_terms, list):
            for term in search_terms[:1]:
                queries.append(f"{title} {term}")
    return list(dict.fromkeys(queries))


def score_language_match(description: str, job_languages: list[str] | None) -> int:
    """Return 0-10 bonus points when JD mentions preferred job languages."""
    if not job_languages:
        return 0
    desc = description.lower()
    hits = 0
    for term in jd_terms_for_languages(job_languages):
        if term.lower() in desc:
            hits += 1
    return min(hits * 3, 10)


def resolve_document_locale(job_languages: list[str] | None, spoken_languages: list[dict] | None) -> str:
    """Pick resume/cover letter language from job search prefs or native language."""
    if job_languages:
        return job_languages[0]
    if spoken_languages:
        for entry in spoken_languages:
            code = entry.get("code")
            if entry.get("level") == "native" and code:
                return str(code)
    return "en"


def detect_response_language(
    job_description: str,
    spoken_languages: list[dict[str, str]] | None,
) -> str:
    """Tell the LLM which language to use for cover letters."""
    codes = [str(e.get("code")) for e in (spoken_languages or []) if e.get("code")]
    if not codes:
        codes = ["pt", "en", "es"]
    scores = {code: score_language_match(job_description, [code]) for code in codes}
    best = max(scores, key=lambda c: scores[c])
    if scores[best] > 0:
        name = language_display_name(best, best)
        return f"Write the cover letter in {name}."
    return "Write in the same language as the job description (Portuguese, English, or Spanish)."
