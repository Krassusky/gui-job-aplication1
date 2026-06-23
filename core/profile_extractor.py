"""Extract structured profile data from CV/resume or LinkedIn text via LLM."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

PROFILE_EXTRACTION_PROMPT = """
You are an expert resume parser. Extract structured profile information from the document below.

Rules:
- Use ONLY information explicitly present in the source. Do NOT invent facts.
- Split full names into first_name and last_name when possible.
- Normalize phone numbers without country code in "phone" and put country code in phone_country_code (default "+1" if unclear).
- bio should be a concise professional summary (2-4 sentences) based on the document headline/summary.
- job_titles: up to 5 realistic target job titles inferred from experience (not fantasy roles).
- keywords_include: up to 15 relevant skills/technologies found in the document.
- experience_levels: choose from "entry", "mid", "senior", "lead", "executive" based on years/roles.
- experience_text: a polished plain-text block summarizing work history as bullet points (for experience files).
- years_experience: estimated total years as a string number if inferable, else empty string.

Output ONLY valid JSON with this exact structure (no markdown fences):
{{
  "profile": {{
    "first_name": "",
    "last_name": "",
    "email": "",
    "phone_country_code": "+1",
    "phone": "",
    "address_line1": "",
    "address_line2": "",
    "city": "",
    "state": "",
    "zip_code": "",
    "country": "",
    "bio": "",
    "linkedin_url": "",
    "portfolio_url": ""
  }},
  "search_criteria": {{
    "job_titles": [],
    "keywords_include": [],
    "experience_levels": []
  }},
  "screening_answers": {{
    "years_experience": ""
  }},
  "experience_text": ""
}}

---
SOURCE ({source_label}):
{document_text}
"""


def _parse_json_response(response: str) -> dict[str, Any]:
    cleaned = response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    return data


def extract_profile_from_text(
    text: str,
    llm_config,
    *,
    source_label: str = "CV",
    max_chars: int = 14000,
) -> dict[str, Any]:
    """Extract profile fields from raw document text using the configured LLM."""
    from core.ai_engine import invoke_llm

    if not text or not text.strip():
        raise ValueError("Document text is empty")

    truncated = text[:max_chars]
    prompt = PROFILE_EXTRACTION_PROMPT.format(
        source_label=source_label,
        document_text=truncated,
    )
    response = invoke_llm(prompt, llm_config, timeout_seconds=120)
    return _parse_json_response(response)


def merge_extracted_into_config(
    config,
    extracted: dict[str, Any],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Merge extracted data into an AppConfig."""
    applied: dict[str, Any] = {"profile": [], "search_criteria": [], "screening_answers": []}

    profile_data = extracted.get("profile") or {}
    for field, value in profile_data.items():
        if value in (None, ""):
            continue
        if not hasattr(config.profile, field):
            continue
        current = getattr(config.profile, field)
        if overwrite or current in (None, ""):
            setattr(config.profile, field, value)
            applied["profile"].append(field)

    sc_data = extracted.get("search_criteria") or {}
    if sc_data.get("job_titles") and (overwrite or not config.search_criteria.job_titles):
        config.search_criteria.job_titles = sc_data["job_titles"][:8]
        applied["search_criteria"].append("job_titles")
    if sc_data.get("keywords_include"):
        if overwrite:
            config.search_criteria.keywords_include = sc_data["keywords_include"][:15]
            applied["search_criteria"].append("keywords_include")
        else:
            existing = set(config.search_criteria.keywords_include)
            new_kw = [k for k in sc_data["keywords_include"] if k not in existing]
            if new_kw:
                config.search_criteria.keywords_include.extend(new_kw[:15])
                applied["search_criteria"].append("keywords_include")
    if sc_data.get("experience_levels") and (overwrite or not config.search_criteria.experience_levels):
        valid = {"entry", "mid", "senior", "lead", "executive"}
        levels = [lvl for lvl in sc_data["experience_levels"] if lvl in valid]
        if levels:
            config.search_criteria.experience_levels = levels
            applied["search_criteria"].append("experience_levels")

    screening = extracted.get("screening_answers") or {}
    years = screening.get("years_experience")
    if years and (overwrite or not config.profile.screening_answers.get("years_experience")):
        config.profile.screening_answers["years_experience"] = str(years)
        applied["screening_answers"].append("years_experience")

    return applied


def save_experience_text(experience_text: str, filename: str = "imported_profile.txt") -> str | None:
    """Write extracted experience text to the experiences folder."""
    if not experience_text or not experience_text.strip():
        return None

    from config.settings import get_data_dir

    exp_dir = get_data_dir() / "profile" / "experiences"
    exp_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w.\-]", "_", filename)
    if not safe_name.endswith(".txt"):
        safe_name += ".txt"
    path = exp_dir / safe_name
    path.write_text(experience_text.strip() + "\n", encoding="utf-8")
    return safe_name
