"""Career workflow — step-by-step job search guide with optional AI analysis."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from config.settings import AppConfig, get_data_dir, save_config
from core.ai_engine import invoke_llm, read_all_experience_files
from core.document_parser import extract_text

logger = logging.getLogger(__name__)

WORKFLOW_STEPS = 6
STATE_FILE = "workflow_state.json"

MANUAL_PROMPTS_PT = {
    "jobs": """Analise meu perfil do LinkedIn e encontre as vagas mais compatíveis com minha experiência.

Liste as 10 melhores oportunidades e, para cada uma, mostre:
- Cargo
- Empresa
- Senioridade
- Modelo de trabalho
- Principais requisitos
- Link da vaga

Ao final, identifique minhas principais forças, gaps e oportunidades de melhoria para aumentar minha empregabilidade.""",
    "recruiters": """Com base no meu perfil do LinkedIn, encontre recrutadores especializados nas áreas em que tenho maior potencial de contratação.

Crie uma lista com:
- Nome
- Empresa
- Cargo
- Perfil do LinkedIn

Priorize recrutadores ativos, que publiquem vagas ou conteúdos com frequência.

Ao final, sugira quais perfis devo seguir primeiro para aumentar minha visibilidade profissional e acesso a oportunidades.""",
    "references": """Com base no meu perfil do LinkedIn, encontre 3 profissionais referência na minha área.

Analise:
- Posicionamento
- Conteúdo
- Diferenciais
- Padrões de autoridade

Ao final, mostre quais práticas posso adaptar para fortalecer meu perfil e aumentar minha visibilidade.""",
}

MANUAL_PROMPTS_ES = {
    "jobs": """Analiza mi perfil de LinkedIn y encuentra las vacantes más compatibles con mi experiencia.

Lista las 10 mejores oportunidades y para cada una muestra: puesto, empresa, seniority, modalidad, requisitos principales y enlace.

Al final, identifica mis fortalezas, brechas y oportunidades de mejora.""",
    "recruiters": """Con base en mi perfil de LinkedIn, encuentra reclutadores especializados en las áreas donde tengo mayor potencial de contratación.

Crea una lista con nombre, empresa, cargo y perfil de LinkedIn. Prioriza reclutadores activos.

Sugiere qué perfiles seguir primero para aumentar mi visibilidad.""",
    "references": """Con base en mi perfil de LinkedIn, encuentra 3 profesionales referencia en mi área.

Analiza posicionamiento, contenido, diferenciales y patrones de autoridad.

Muestra qué prácticas puedo adaptar para fortalecer mi perfil.""",
}

MANUAL_PROMPTS_EN = {
    "jobs": """Analyze my LinkedIn profile and find the job openings most compatible with my experience.

List the 10 best opportunities and for each show: role, company, seniority, work model, key requirements, and job link.

At the end, identify my main strengths, gaps, and improvement opportunities.""",
    "recruiters": """Based on my LinkedIn profile, find recruiters specialized in areas where I have the highest hiring potential.

Create a list with name, company, role, and LinkedIn profile. Prioritize active recruiters who post jobs frequently.

Suggest which profiles I should follow first to increase visibility.""",
    "references": """Based on my LinkedIn profile, find 3 reference professionals in my field.

Analyze their positioning, content, differentiators, and authority patterns.

Show which practices I can adapt to strengthen my profile.""",
}


def _state_path() -> Path:
    return get_data_dir() / STATE_FILE


def load_workflow_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {"current_step": 1, "completed_steps": [], "analyses": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("current_step", 1)
        data.setdefault("completed_steps", [])
        data.setdefault("analyses", {})
        return data
    except Exception as e:
        logger.warning("Could not load workflow state: %s", e)
        return {"current_step": 1, "completed_steps": [], "analyses": {}}


def save_workflow_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def mark_step_complete(step: int) -> dict[str, Any]:
    state = load_workflow_state()
    completed = set(state.get("completed_steps", []))
    completed.add(step)
    state["completed_steps"] = sorted(completed)
    if step < WORKFLOW_STEPS:
        state["current_step"] = step + 1
    save_workflow_state(state)
    return state


def set_current_step(step: int) -> dict[str, Any]:
    state = load_workflow_state()
    state["current_step"] = max(1, min(step, WORKFLOW_STEPS))
    save_workflow_state(state)
    return state


def get_manual_prompts(locale: str = "pt") -> dict[str, str]:
    if locale.startswith("pt"):
        return MANUAL_PROMPTS_PT
    if locale.startswith("es"):
        return MANUAL_PROMPTS_ES
    return MANUAL_PROMPTS_EN


def _response_language(locale: str) -> str:
    if locale.startswith("pt"):
        return "Portuguese"
    if locale.startswith("es"):
        return "Spanish"
    return "English"


def gather_profile_context(config: AppConfig | None) -> str:
    """Build text context from profile, CV, and experience files."""
    parts: list[str] = []

    if config:
        p = config.profile
        parts.append(
            f"Nome: {p.full_name}\n"
            f"Email: {p.email}\n"
            f"Localização: {p.location}\n"
            f"Bio: {p.bio}\n"
            f"LinkedIn: {p.linkedin_url or 'não informado'}"
        )
        sc = config.search_criteria
        if sc.job_titles:
            parts.append(f"Cargos desejados (configurados): {', '.join(sc.job_titles)}")
        if sc.keywords_include:
            parts.append(f"Palavras-chave: {', '.join(sc.keywords_include)}")
        if sc.job_languages:
            parts.append(f"Idiomas de busca: {', '.join(sc.job_languages)}")
        spoken = config.profile.spoken_languages or []
        if spoken:
            from core.languages import format_languages_line
            parts.append(f"Idiomas falados: {format_languages_line(spoken, 'pt')}")

    data_dir = get_data_dir()
    exp_dir = data_dir / "profile" / "experiences"
    exp_text = read_all_experience_files(exp_dir)
    if exp_text.strip():
        parts.append(f"--- Experiências (arquivos) ---\n{exp_text[:12000]}")

    resume_path = _find_resume_path(config)
    if resume_path:
        try:
            cv_text = extract_text(resume_path)[:8000]
            if cv_text.strip():
                parts.append(f"--- Currículo ({resume_path.name}) ---\n{cv_text}")
        except Exception as e:
            logger.warning("Could not read resume for workflow: %s", e)

    return "\n\n".join(parts) if parts else ""


def _find_resume_path(config: AppConfig | None) -> Path | None:
    if config and config.profile.fallback_resume_path:
        p = Path(config.profile.fallback_resume_path)
        if p.exists():
            return p
    data_dir = get_data_dir()
    for ext in (".pdf", ".docx"):
        candidate = data_dir / f"default_resume{ext}"
        if candidate.exists():
            return candidate
    return None


def check_readiness(config: AppConfig | None) -> dict[str, Any]:
    ctx = gather_profile_context(config)
    has_profile = bool(config and config.profile.first_name and config.profile.email)
    has_cv = _find_resume_path(config) is not None
    exp_dir = get_data_dir() / "profile" / "experiences"
    exp_files = [f for f in exp_dir.glob("*.txt") if f.name.lower() != "readme.txt"] if exp_dir.exists() else []
    has_experience = len(exp_files) > 0
    ai_available = bool(config and config.llm.api_key and config.llm.provider)
    has_languages = bool(
        config
        and (config.profile.spoken_languages or config.search_criteria.job_languages)
    )

    return {
        "has_profile": has_profile,
        "has_cv": has_cv,
        "has_experience": has_experience,
        "has_context": len(ctx.strip()) > 100,
        "ai_available": ai_available,
        "has_languages": has_languages,
        "experience_file_count": len(exp_files),
        "ready_for_analysis": has_profile and (has_cv or has_experience),
    }


def _parse_json_block(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def analyze_jobs(config: AppConfig, locale: str = "pt") -> dict[str, Any]:
    context = gather_profile_context(config)
    if len(context.strip()) < 50:
        raise ValueError("profile_incomplete")

    lang = _response_language(locale)
    prompt = f"""You are a career coach. Analyze this candidate profile and suggest a job search strategy.
Reply in {lang}. Return ONLY valid JSON (no markdown fences) with this structure:
{{
  "strengths": ["..."],
  "gaps": ["..."],
  "improvements": ["..."],
  "suggested_titles": ["..."],
  "suggested_keywords": ["..."],
  "suggested_locations": ["..."],
  "seniority": "junior|mid|senior|staff",
  "summary": "2-3 paragraph markdown summary"
}}

Profile:
{context}
"""
    raw = invoke_llm(prompt, config.llm, timeout_seconds=120)
    parsed = _parse_json_block(raw)
    if parsed:
        return {"mode": "ai", "content": parsed, "raw": raw}

    return {
        "mode": "ai",
        "content": {"summary": raw, "suggested_titles": [], "suggested_keywords": [], "suggested_locations": []},
        "raw": raw,
    }


def analyze_recruiters(config: AppConfig, locale: str = "pt") -> dict[str, Any]:
    context = gather_profile_context(config)
    lang = _response_language(locale)
    prompt = f"""You are a networking coach. Based on this profile, create a recruiter outreach plan.
Reply in {lang} as markdown with sections:
## Recruiter search strategy
## Types of recruiters to target
## 3 connection message templates (in {lang})
## Weekly networking routine (15 min/day)

Profile:
{context[:10000]}
"""
    raw = invoke_llm(prompt, config.llm, timeout_seconds=90)
    return {"mode": "ai", "content": raw}


def analyze_references(config: AppConfig, locale: str = "pt") -> dict[str, Any]:
    context = gather_profile_context(config)
    lang = _response_language(locale)
    prompt = f"""You are a LinkedIn branding coach. Based on this profile, explain how to find and learn from reference profiles.
Reply in {lang} as markdown with sections:
## What to look for in 3 reference profiles
## LinkedIn search filters to use
## Profile improvements (headline, about, featured)
## Content ideas (3 post topics)

Profile:
{context[:10000]}
"""
    raw = invoke_llm(prompt, config.llm, timeout_seconds=90)
    return {"mode": "ai", "content": raw}


def apply_search_suggestions(
    config: AppConfig,
    titles: list[str] | None = None,
    keywords: list[str] | None = None,
    locations: list[str] | None = None,
) -> AppConfig:
    if titles:
        existing = list(config.search_criteria.job_titles)
        for t in titles:
            if t and t not in existing:
                existing.append(t)
        config.search_criteria.job_titles = existing[:10]

    if keywords:
        existing = list(config.search_criteria.keywords_include)
        for k in keywords:
            if k and k not in existing:
                existing.append(k)
        config.search_criteria.keywords_include = existing[:20]

    if locations:
        existing = list(config.search_criteria.locations)
        for loc in locations:
            if loc and loc not in existing:
                existing.append(loc)
        config.search_criteria.locations = existing[:10]

    save_config(config)
    return config


def store_analysis(step_key: str, data: dict[str, Any]) -> None:
    state = load_workflow_state()
    analyses = state.setdefault("analyses", {})
    analyses[step_key] = data
    save_workflow_state(state)
