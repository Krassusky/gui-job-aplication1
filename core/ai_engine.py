"""AI Engine — generates tailored resumes and cover letters via LLM APIs.

Implements: FR-031 (AI availability check), FR-032 (document generation),
            FR-074 (multi-provider LLM).

Supports Anthropic, OpenAI, Google (Gemini), DeepSeek, Groq, OpenRouter, and Ollama as providers.
Falls back to local Ollama when cloud limits are hit (if enabled).
Falls back to static templates when no API key is configured.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Default models per provider
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
    "deepseek": "deepseek-chat",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
    "ollama": "llama3.2",
}

OLLAMA_BASE_URL = os.environ.get("AUTOAPPLY_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")

# HTTP status codes that trigger fallback to local Ollama
FALLBACK_STATUS_CODES = {401, 402, 429}

# API endpoints per provider
API_ENDPOINTS = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/chat/completions",
    "google": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}

RESUME_PROMPT = """
You are an expert resume writer. Create a tailored, ATS-optimised resume for this specific job.

Instructions:
- Read ALL experience files below carefully
- Select only experiences and skills most relevant to THIS job
- Quantify achievements wherever numbers appear in the raw notes
- Use strong action verbs
- Keep content to one page worth of text
- Do NOT invent or exaggerate anything not present in the experience files

Output format — Markdown only, no preamble, no explanation:

# [Full Name]
[email] | [phone] | [location] | [linkedin if provided] | [portfolio if provided]

## Summary
2-3 sentences tailored specifically to this role and company.

## Experience
### [Job Title] — [Company] ([Start Year] - [End Year or Present])
- Achievement bullet using numbers where available
- Achievement bullet
...

## Skills
Comma-separated, relevant skills only.

## Languages
{languages_section}

## Education
[Degree] — [Institution] ([Year])

Omit any section for which there is no information.

---
EXPERIENCE FILES:
{experience_files_content}

---
JOB DESCRIPTION:
{job_description}

---
APPLICANT:
Name: {full_name}
Email: {email}
Phone: {phone}
Location: {location}
LinkedIn: {linkedin_url}
Portfolio: {portfolio_url}
Languages: {languages_line}
"""

KB_RESUME_PROMPT = """
You are an expert resume writer. Create a polished, ATS-optimised resume using ONLY the data provided below.

STRICT RULES:
- Use ONLY the experiences, skills, education, projects, and certifications listed below
- Do NOT invent, fabricate, or embellish ANY information
- Do NOT add companies, roles, skills, or achievements not present in the data
- Do NOT guess dates, locations, or titles — use exactly what is provided
- You MAY rephrase and reword bullets for clarity, readability, impact, and ATS optimization
- You MAY use synonyms from the job description to better align bullet phrasing
- You MAY combine or split related bullets from the same role for better flow
- You MAY reorder content to best match the job description
- You MAY omit entries that are clearly irrelevant to this specific job
- Quantify achievements where numbers are already present in the data

PAGE LENGTH RULES — THIS IS CRITICAL:
- The resume MUST fill exactly ONE full US Letter page (no more, no less)
- Use the highest-ranked data first, then include lower-ranked data until the page is full
- Every experience role MUST have at least 2 bullet points — expand by rephrasing or splitting if needed
- If space remains, add more bullet points to the most relevant roles or include additional projects
- If too long, trim the least relevant bullets from the bottom — but keep at least 2 per role

Output format — Markdown only, no preamble, no explanation:

# {full_name}
{email} | {phone} | {location}{linkedin_line}

## Summary
{summary_text}

## Education
### [Institution] | [Location]
[Degree] | [Dates]

## Skills
**[Category]**: [comma-separated skills]

## Experience
### [Company] | [Location]
**[Job Title]** | [Dates]
- Achievement bullet (from provided data only)
- At least 2 bullets per role

## Projects
### [Project Name]
- Description bullet (from provided data only)

## Certifications
- [Certification name]

Omit any section that has no data.

---
JOB DESCRIPTION:
{job_description}

---
PROVIDED RESUME DATA (use ONLY this — do not add anything else):

{kb_data}
"""

COVER_LETTER_PROMPT = """
You are an expert career coach. Write a cover letter for this job application.

Instructions:
- 3 paragraphs, professional but not stiff
- Reference specific details from the job description
- Use relevant experiences from the experience files
- Do NOT use filler phrases like "I am excited to apply" or "I am a perfect fit"
- Do NOT repeat the resume — add context and personality
- Match tone to the company culture inferred from the job description
- {language_instruction}
- Output ONLY the cover letter body — no date, no address, no salutation header, no sign-off

---
EXPERIENCE FILES:
{experience_files_content}

---
JOB DESCRIPTION:
{job_description}

---
APPLICANT:
Name: {full_name}
Bio / tone preference: {bio}
"""


def get_ollama_base_url() -> str:
    """Return the configured Ollama API base URL."""
    return OLLAMA_BASE_URL


def get_ollama_model(llm_config=None) -> str:
    """Resolve the Ollama model name from config or defaults."""
    if llm_config:
        if getattr(llm_config, "ollama_model", None):
            return llm_config.ollama_model
        if llm_config.provider == "ollama" and llm_config.model:
            return llm_config.model
    return os.environ.get("AUTOAPPLY_OLLAMA_MODEL", DEFAULT_MODELS["ollama"])


def ollama_fallback_enabled(llm_config) -> bool:
    """Return True when cloud failures should fall back to local Ollama."""
    if os.environ.get("AUTOAPPLY_OLLAMA_FALLBACK", "").lower() in ("1", "true", "yes"):
        return True
    return bool(getattr(llm_config, "ollama_fallback_enabled", False))


def check_ollama_available(timeout: int = 3) -> bool:
    """Ping the local Ollama server."""
    try:
        resp = requests.get(f"{get_ollama_base_url()}/api/tags", timeout=timeout)
        return resp.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def check_ai_available(llm_config) -> bool:
    """Check if an LLM provider is configured or Ollama is reachable.

    Args:
        llm_config: LLMConfig with provider and api_key fields.

    Returns:
        True if a cloud provider has an API key, Ollama is the active provider,
        or Ollama fallback is enabled and the local server responds.
    """
    if not llm_config:
        return check_ollama_available()
    active = getattr(llm_config, "get_active_entry", None)
    if callable(active):
        entry = llm_config.get_active_entry()
        if entry:
            if entry.provider == "ollama":
                return check_ollama_available()
            if entry.provider and entry.api_key:
                return True
    if llm_config.provider == "ollama":
        return check_ollama_available()
    if llm_config.provider and llm_config.api_key:
        return True
    if ollama_fallback_enabled(llm_config) and check_ollama_available():
        return True
    return False


class APIKeyValidationResult:
    """Result of an API key validation attempt."""

    __slots__ = ("valid", "message", "error_code")

    def __init__(self, valid: bool, message: str = "", error_code: str = ""):
        self.valid = valid
        self.message = message
        self.error_code = error_code

    def as_dict(self) -> dict[str, str | bool]:
        payload: dict[str, str | bool] = {"valid": self.valid}
        if self.message:
            payload["message"] = self.message
        if self.error_code:
            payload["error_code"] = self.error_code
        return payload


def _classify_validation_error(error: Exception) -> APIKeyValidationResult:
    """Map provider API errors to user-facing validation results."""
    msg = str(error)
    if "(401)" in msg or "(403)" in msg:
        return APIKeyValidationResult(
            False,
            "Invalid API key. Check that the key is correct and active.",
            "invalid_key",
        )
    if "(402)" in msg:
        return APIKeyValidationResult(
            False,
            "API key is recognized but the account has insufficient balance. "
            "Add credits to your provider account and try again.",
            "insufficient_balance",
        )
    if "(404)" in msg and "model" in msg.lower():
        return APIKeyValidationResult(
            False,
            "API key works but the selected model was not found. "
            "Leave model blank to use the default or choose another model.",
            "invalid_model",
        )
    return APIKeyValidationResult(
        False,
        msg or "Could not validate API key with the selected provider.",
        "provider_error",
    )


def validate_api_key(
    provider: str, api_key: str, model: str | None = None
) -> APIKeyValidationResult:
    """Validate an API key by making a minimal test request.

    Args:
        provider: One of "anthropic", "openai", "google", "deepseek".
        api_key: The API key to validate.
        model: Optional model name override.

    Returns:
        APIKeyValidationResult with validity, message, and error_code.
    """
    model = model or DEFAULT_MODELS.get(provider, "")
    if provider == "ollama":
        if check_ollama_available():
            return APIKeyValidationResult(True, "Ollama server is reachable", "ok")
        return APIKeyValidationResult(
            False,
            f"Cannot reach Ollama at {get_ollama_base_url()}",
            "provider_error",
        )
    try:
        _call_llm(provider, api_key, model, "Reply with OK", timeout=15)
        return APIKeyValidationResult(True, "API key is valid", "ok")
    except Exception as e:
        logger.debug("API key validation failed for %s: %s", provider, e)
        return _classify_validation_error(e)


# Retry configuration (D-6)
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _call_llm(
    provider: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout: int = 120,
) -> str:
    """Call an LLM API with retry and exponential backoff (D-6).

    Retries up to MAX_RETRIES times on transient errors (429, 5xx, network
    errors) with exponential backoff (1s, 2s, 4s). Non-retryable errors
    (401, 403, 400) fail immediately.

    Args:
        provider: One of "anthropic", "openai", "google", "deepseek".
        api_key: API key for the provider.
        model: Model identifier.
        prompt: The prompt to send.
        timeout: Request timeout in seconds.

    Returns:
        The generated text content.

    Raises:
        RuntimeError: If the API call fails after all retries.
    """
    def call_fn() -> str:
        if provider == "anthropic":
            return _call_anthropic(api_key, model, prompt, timeout)
        elif provider == "google":
            return _call_google(api_key, model, prompt, timeout)
        elif provider == "ollama":
            return _call_ollama(model, prompt, timeout)
        elif provider in ("openai", "deepseek", "groq", "openrouter"):
            return _call_openai_compatible(provider, api_key, model, prompt, timeout)
        raise RuntimeError(f"Unsupported LLM provider: {provider}")

    if provider not in (
        "anthropic", "google", "openai", "deepseek", "groq", "openrouter", "ollama",
    ):
        raise RuntimeError(f"Unsupported LLM provider: {provider}")

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return call_fn()
        except RuntimeError as e:
            last_error = e
            # Don't retry auth/client errors
            error_msg = str(e)
            if any(f"({code})" in error_msg for code in (400, 401, 402, 403, 404)):
                raise
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "LLM call attempt %d/%d failed (%s), retrying in %.1fs...",
                    attempt + 1, MAX_RETRIES + 1, e, delay,
                )
                time.sleep(delay)
        except (requests.ConnectionError, requests.Timeout) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "LLM call attempt %d/%d failed (%s), retrying in %.1fs...",
                    attempt + 1, MAX_RETRIES + 1, type(e).__name__, delay,
                )
                time.sleep(delay)

    raise RuntimeError(f"LLM call failed after {MAX_RETRIES + 1} attempts: {last_error}")


def _call_anthropic(api_key: str, model: str, prompt: str, timeout: int) -> str:
    """Call Anthropic Messages API."""
    resp = requests.post(
        API_ENDPOINTS["anthropic"],
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        _raise_api_error("Anthropic", resp)
    data = resp.json()
    return str(data["content"][0]["text"]).strip()


def _call_openai_compatible(
    provider: str, api_key: str, model: str, prompt: str, timeout: int
) -> str:
    """Call OpenAI-compatible API (OpenAI, DeepSeek, Groq, OpenRouter)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/autoapply"
        headers["X-Title"] = "AutoApply"

    resp = requests.post(
        API_ENDPOINTS[provider],
        headers=headers,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8192,
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        _raise_api_error(provider.title(), resp)
    data = resp.json()
    return str(data["choices"][0]["message"]["content"]).strip()


def _call_google(api_key: str, model: str, prompt: str, timeout: int) -> str:
    """Call Google Gemini API."""
    url = API_ENDPOINTS["google"].format(model=model)
    resp = requests.post(
        url,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 4096},
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        _raise_api_error("Google", resp)
    data = resp.json()
    return str(data["candidates"][0]["content"]["parts"][0]["text"]).strip()


def _call_ollama(model: str, prompt: str, timeout: int) -> str:
    """Call a local Ollama server via its generate API."""
    resp = requests.post(
        f"{get_ollama_base_url()}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        _raise_api_error("Ollama", resp)
    data = resp.json()
    return str(data.get("response", "")).strip()


def _extract_status_code(error: Exception) -> int | None:
    """Parse an HTTP status code from a RuntimeError message."""
    msg = str(error)
    for code in (*FALLBACK_STATUS_CODES, 400, 403, 404, 500, 502, 503, 504):
        if f"({code})" in msg:
            return code
    return None


def _should_fallback_to_ollama(error: Exception) -> bool:
    """Return True when a cloud provider error should trigger Ollama fallback."""
    code = _extract_status_code(error)
    if code in FALLBACK_STATUS_CODES:
        return True
    if code is None and isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return True
    return False


def _raise_api_error(provider: str, resp: requests.Response) -> None:
    """Extract error message from API response and raise RuntimeError."""
    try:
        body = resp.json()
        msg = body.get("error", {})
        if isinstance(msg, dict):
            msg = msg.get("message", resp.text)
    except Exception as e:
        logger.debug("Failed to parse API error response: %s", e)
        msg = resp.text
    raise RuntimeError(f"{provider} API error ({resp.status_code}): {msg}")


def invoke_llm_with_fallback(
    prompt: str,
    llm_config,
    timeout_seconds: int = 120,
    *,
    allow_fallback: bool | None = None,
) -> str:
    """Generate text using the configured provider, optionally falling back to Ollama.

    Tries the configured cloud provider first. On rate-limit, auth, balance errors,
    or network failure, falls back to local Ollama when enabled.
    """
    if not llm_config:
        raise RuntimeError(
            "No AI provider configured. Add an API key in Settings → AI Provider."
        )

    provider = llm_config.provider or ""
    api_key = llm_config.api_key or ""
    model = llm_config.model or DEFAULT_MODELS.get(provider, "")

    if provider == "ollama":
        ollama_model = get_ollama_model(llm_config)
        return _call_llm("ollama", "", ollama_model, prompt, timeout_seconds)

    if not api_key:
        if ollama_fallback_enabled(llm_config) and check_ollama_available():
            logger.warning("No cloud API key configured; using Ollama fallback")
            ollama_model = get_ollama_model(llm_config)
            return _call_llm("ollama", "", ollama_model, prompt, timeout_seconds)
        raise RuntimeError(
            "No AI provider configured. Add an API key in Settings → AI Provider."
        )

    use_fallback = (
        ollama_fallback_enabled(llm_config) if allow_fallback is None else allow_fallback
    )

    try:
        return _call_llm(provider, api_key, model, prompt, timeout_seconds)
    except Exception as e:
        if not use_fallback or not _should_fallback_to_ollama(e):
            raise
        if not check_ollama_available():
            logger.error("Cloud LLM failed and Ollama is not reachable")
            raise
        logger.warning(
            "Cloud LLM failed (%s); falling back to Ollama at %s",
            e,
            get_ollama_base_url(),
        )
        ollama_model = get_ollama_model(llm_config)
        return _call_llm("ollama", "", ollama_model, prompt, timeout_seconds)


def invoke_llm(prompt: str, llm_config, timeout_seconds: int = 120) -> str:
    """Generate text using the configured LLM provider (with optional Ollama fallback)."""
    return invoke_llm_with_fallback(prompt, llm_config, timeout_seconds)


def read_all_experience_files(experience_dir: Path) -> str:
    """Read all .txt files from experience directory, excluding README.txt.

    Files are sorted alphabetically and concatenated with section separators.

    Args:
        experience_dir: Path to directory containing .txt files.

    Returns:
        Concatenated content string, or empty string if no files found.
    """
    if not experience_dir.exists():
        return ""

    parts: list[str] = []
    for f in sorted(experience_dir.glob("*.txt")):
        if f.name.lower() == "readme.txt":
            continue
        try:
            content = f.read_text(encoding="utf-8")
            parts.append(f"=== {f.name} ===\n{content}")
        except (UnicodeDecodeError, OSError) as e:
            logger.warning("Skipping unreadable experience file %s: %s", f.name, e)

    return "\n\n".join(parts)


def generate_documents(
    job,
    profile,
    experience_dir: Path,
    output_dir_resumes: Path,
    output_dir_cover_letters: Path,
    llm_config=None,
    skip_cover_letter: bool = False,
) -> tuple[Path, Path | None, dict]:
    """Generate tailored resume and cover letter for a job application.

    Reads experience files, calls the configured LLM for resume (and
    optionally cover letter), saves outputs to disk, and returns paths
    plus version metadata.

    Args:
        job: Object with ``.id`` (str), ``.raw.company`` (str),
             ``.raw.description`` (str).
        profile: UserProfile with full_name, email, phone, location,
                 linkedin_url, portfolio_url, bio.
        experience_dir: Path to experience .txt files.
        output_dir_resumes: Where to save resume .md and .pdf files.
        output_dir_cover_letters: Where to save cover letter .txt files.
        llm_config: LLMConfig with provider, api_key, model.
        skip_cover_letter: If True, skip cover letter generation.

    Returns:
        Tuple of (resume_pdf_path, cover_letter_txt_path | None, version_meta).
        version_meta contains resume_md_path, resume_pdf_path, llm_provider,
        and llm_model for resume version recording (FR-118).

    Raises:
        RuntimeError: If LLM invocation fails.
    """
    from core.languages import format_languages_line
    from core.resume_renderer import render_resume_to_pdf

    experience_content = read_all_experience_files(experience_dir)
    languages_line = format_languages_line(getattr(profile, "spoken_languages", None), "pt")
    languages_section = (
        languages_line
        if languages_line
        else "List only languages evidenced in experience files."
    )

    safe_company = job.raw.company.replace(" ", "-").lower()
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_name = f"{job.id}_{safe_company}_{date_str}"

    # Ensure output directories exist
    output_dir_resumes.mkdir(parents=True, exist_ok=True)
    output_dir_cover_letters.mkdir(parents=True, exist_ok=True)

    # Capture LLM provider/model for version tracking (FR-118)
    llm_provider = getattr(llm_config, "provider", None) if llm_config else None
    llm_model = getattr(llm_config, "model", None) if llm_config else None

    # Generate resume via LLM
    resume_md_text = invoke_llm(RESUME_PROMPT.format(
        experience_files_content=experience_content,
        job_description=job.raw.description,
        full_name=profile.full_name,
        email=profile.email,
        phone=profile.phone_full,
        location=profile.location,
        linkedin_url=profile.linkedin_url or "N/A",
        portfolio_url=profile.portfolio_url or "N/A",
        languages_line=languages_line or "N/A",
        languages_section=languages_section,
    ), llm_config)

    # Save resume Markdown + PDF
    resume_md_path = output_dir_resumes / f"{base_name}.md"
    resume_pdf_path = output_dir_resumes / f"{base_name}.pdf"
    resume_md_path.write_text(resume_md_text, encoding="utf-8")
    render_resume_to_pdf(resume_md_text, resume_pdf_path)

    # Generate and save cover letter (unless disabled)
    cl_path = None
    if not skip_cover_letter:
        from core.languages import detect_response_language

        language_instruction = detect_response_language(
            job.raw.description, getattr(profile, "spoken_languages", None)
        )
        cover_letter_text = invoke_llm(COVER_LETTER_PROMPT.format(
            experience_files_content=experience_content,
            job_description=job.raw.description,
            full_name=profile.full_name,
            bio=profile.bio,
            language_instruction=language_instruction,
        ), llm_config)
        cl_path = output_dir_cover_letters / f"{base_name}.txt"
        cl_path.write_text(cover_letter_text, encoding="utf-8")

    version_meta = {
        "resume_md_path": str(resume_md_path),
        "resume_pdf_path": str(resume_pdf_path),
        "llm_provider": llm_provider,
        "llm_model": llm_model,
    }

    return resume_pdf_path, cl_path, version_meta


def _format_kb_data_for_prompt(context: dict) -> str:
    """Format structured KB context into a text block for the LLM prompt.

    Takes the same context dict produced by resume_assembler._build_context()
    and serializes it into a human-readable text block that the LLM can use.
    """
    lines: list[str] = []

    # Education
    for entry in context.get("education", []):
        inst = entry.get("institution", "")
        loc = entry.get("location", "")
        degree = entry.get("degree", "")
        dates = entry.get("dates", "")
        lines.append(f"EDUCATION: {inst} | {loc} | {degree} | {dates}")

    # Skills
    for group in context.get("skills", []):
        cat = group.get("category", "")
        entries = group.get("entries", "")
        lines.append(f"SKILLS ({cat}): {entries}")

    # Experience
    for comp in context.get("experience", []):
        company = comp.get("company", "")
        loc = comp.get("location", "")
        for role in comp.get("roles", []):
            title = role.get("title", "")
            dates = role.get("dates", "")
            lines.append(f"EXPERIENCE: {company} | {loc} | {title} | {dates}")
            for bullet in role.get("bullets", []):
                lines.append(f"  - {bullet}")

    # Projects
    for proj in context.get("projects", []):
        name = proj.get("name", "")
        lines.append(f"PROJECT: {name}")
        for bullet in proj.get("bullets", []):
            lines.append(f"  - {bullet}")

    # Certifications
    for entry in context.get("certifications", []):
        lines.append(f"CERTIFICATION: {entry.get('text', '')}")

    return "\n".join(lines)


def generate_resume_from_kb(
    context: dict,
    jd_text: str,
    llm_config,
) -> str:
    """Generate a resume markdown from structured KB data via LLM.

    The LLM is strictly instructed to use ONLY the provided KB data
    and not invent any experiences, skills, or achievements.

    Args:
        context: Structured context dict from _build_context() with
            name, email, phone, location, summary, experience, education,
            skills, projects, certifications.
        jd_text: Job description to tailor against.
        llm_config: LLMConfig with provider, api_key, model.

    Returns:
        Resume content as markdown string.

    Raises:
        RuntimeError: If LLM invocation fails.
    """
    kb_data = _format_kb_data_for_prompt(context)
    summary = context.get("summary", "")
    linkedin = context.get("linkedin_url", "")
    linkedin_line = f" | {linkedin}" if linkedin else ""

    prompt = KB_RESUME_PROMPT.format(
        full_name=context.get("name", ""),
        email=context.get("email", ""),
        phone=context.get("phone", ""),
        location=context.get("location", ""),
        linkedin_line=linkedin_line,
        summary_text=summary if summary else "Write a 2-3 sentence summary tailored to the job, based ONLY on the provided data.",
        job_description=jd_text,
        kb_data=kb_data,
    )

    return invoke_llm(prompt, llm_config)
