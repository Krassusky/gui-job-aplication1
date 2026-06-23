"""Profile and experience file routes.

Implements: FR-011 (experience file CRUD), FR-012 (profile status),
            profile import from CV and LinkedIn.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

import app_state
from config.settings import LLMConfig, get_data_dir, load_config, save_config
from core.ai_engine import check_ai_available as llm_is_configured
from core.document_parser import extract_text
from core.i18n import t
from core.linkedin_importer import parse_linkedin_export_zip, scrape_linkedin_profile
from core.profile_extractor import (
    extract_profile_from_text,
    merge_extracted_into_config,
    save_experience_text,
)
from routes.bot import check_ai_available

logger = logging.getLogger(__name__)

profile_bp = Blueprint("profile", __name__)

_ALLOWED_IMPORT_EXT = {".pdf", ".docx", ".doc", ".txt", ".md"}
_MAX_IMPORT_SIZE = 8 * 1024 * 1024  # 8 MB
_MAX_ZIP_SIZE = 25 * 1024 * 1024  # 25 MB


def validate_filename(filename: str) -> str | None:
    """Returns error message if filename is invalid, None if valid."""
    if not filename:
        return t("errors.filename_required")
    if ".." in filename or "/" in filename or "\\" in filename:
        return t("errors.invalid_filename")
    if not app_state.SAFE_FILENAME_RE.match(filename):
        return t("errors.invalid_filename_detail")
    return None


@profile_bp.route("/api/profile/experiences", methods=["GET"])
def list_experiences():
    experiences_dir = get_data_dir() / "profile" / "experiences"
    experiences_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict] = []
    for file_path in sorted(experiences_dir.glob("*.txt")):
        stat = file_path.stat()
        files.append({
            "name": file_path.name,
            "content": file_path.read_text(encoding="utf-8"),
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return jsonify({"files": files})


@profile_bp.route("/api/profile/experiences", methods=["POST"])
def create_experience():
    data = request.get_json()
    if not data or "filename" not in data or "content" not in data:
        return jsonify({"error": t("errors.filename_content_required")}), 400
    filename: str = data["filename"]
    content: str = data["content"]
    error = validate_filename(filename)
    if error:
        return jsonify({"error": error}), 400
    experiences_dir = get_data_dir() / "profile" / "experiences"
    experiences_dir.mkdir(parents=True, exist_ok=True)
    (experiences_dir / filename).write_text(content, encoding="utf-8")
    return jsonify({"success": True})


@profile_bp.route("/api/profile/experiences/<filename>", methods=["PUT"])
def update_experience(filename: str):
    error = validate_filename(filename)
    if error:
        return jsonify({"error": error}), 400
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": t("errors.content_required")}), 400
    content: str = data["content"]
    experiences_dir = get_data_dir() / "profile" / "experiences"
    file_path = experiences_dir / filename
    if not file_path.exists():
        return jsonify({"error": t("errors.file_not_found")}), 404
    file_path.write_text(content, encoding="utf-8")
    return jsonify({"success": True})


@profile_bp.route("/api/profile/experiences/<filename>", methods=["DELETE"])
def delete_experience(filename: str):
    error = validate_filename(filename)
    if error:
        return jsonify({"error": error}), 400
    experiences_dir = get_data_dir() / "profile" / "experiences"
    file_path = experiences_dir / filename
    if not file_path.exists():
        return jsonify({"error": t("errors.file_not_found")}), 404
    file_path.unlink()
    return jsonify({"success": True})


@profile_bp.route("/api/profile/status", methods=["GET"])
def profile_status():
    experiences_dir = get_data_dir() / "profile" / "experiences"
    experiences_dir.mkdir(parents=True, exist_ok=True)
    txt_files = list(experiences_dir.glob("*.txt"))
    total_words = 0
    for file_path in txt_files:
        total_words += len(file_path.read_text(encoding="utf-8").split())
    return jsonify({
        "file_count": len(txt_files),
        "total_words": total_words,
        "ai_available": check_ai_available(),
    })


def _llm_from_request_body(body: dict | None) -> LLMConfig | None:
    llm_data = (body or {}).get("llm") or {}
    provider = llm_data.get("provider") or body.get("provider") if body else ""
    api_key = llm_data.get("api_key") or (body.get("api_key") if body else "")
    model = llm_data.get("model") or (body.get("model") if body else "")
    if provider and api_key:
        return LLMConfig(provider=provider, api_key=api_key, model=model or "")
    return None


def _llm_from_form() -> LLMConfig | None:
    provider = request.form.get("provider", "")
    api_key = request.form.get("api_key", "")
    model = request.form.get("model", "")
    if provider and api_key:
        return LLMConfig(provider=provider, api_key=api_key, model=model or "")
    return None


def _resolve_llm_for_import(json_body: dict | None = None):
    """Return (llm_config, app_config) for import endpoints."""
    config = load_config()
    if config and llm_is_configured(config.llm):
        return config.llm, config

    inline = _llm_from_request_body(json_body) or _llm_from_form()
    if inline and inline.provider and inline.api_key:
        return inline, config

    return None, config


def _apply_import(extracted: dict, config, source: str) -> dict:
    applied = merge_extracted_into_config(config, extracted, overwrite=True)
    exp_file = None
    exp_text = extracted.get("experience_text") or ""
    if exp_text.strip():
        exp_file = save_experience_text(
            exp_text,
            filename=f"imported_{source}.txt",
        )
    save_config(config)
    return {"applied": applied, "experience_file": exp_file}


@profile_bp.route("/api/profile/import-cv", methods=["POST"])
def import_cv():
    """Extract profile fields from an uploaded CV/resume."""
    llm_config, config = _resolve_llm_for_import()
    if not llm_config:
        return jsonify({"error": t("errors.ai_required_for_import")}), 400

    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": t("errors.no_file_provided")}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in _ALLOWED_IMPORT_EXT:
        return jsonify({"error": t("errors.unsupported_import_format")}), 400

    data = f.read()
    if len(data) > _MAX_IMPORT_SIZE:
        return jsonify({"error": t("errors.file_too_large")}), 400

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        raw_text = extract_text(tmp_path)
        extracted = extract_profile_from_text(
            raw_text,
            llm_config,
            source_label="CV/Resume",
        )
    except Exception as e:
        logger.exception("CV import failed")
        return jsonify({"error": str(e)}), 500
    finally:
        tmp_path.unlink(missing_ok=True)

    apply_now = request.args.get("apply", "").lower() in ("1", "true", "yes")
    result = {"extracted": extracted, "source": "cv"}
    if apply_now and config:
        result.update(_apply_import(extracted, config, "cv"))

    return jsonify(result)


def _linkedin_import_error_message(exc: Exception) -> str:
    """Return a short user-facing message for LinkedIn import failures."""
    msg = str(exc)
    if "Not logged in to LinkedIn" in msg:
        return msg
    if "Target page, context or browser has been closed" in msg:
        return (
            "The login browser closed while importing. "
            "Click Open LinkedIn Login, wait until it shows Connected, then try Import again."
        )
    if "exitCode=21" in msg or "launch_persistent_context" in msg:
        return (
            "Could not open the LinkedIn browser (profile in use). "
            "Close any AutoApply Chrome window, click Open LinkedIn Login, then Import from LinkedIn."
        )
    if len(msg) > 240:
        return (
            "LinkedIn import failed. Sign in via Open LinkedIn Login first, "
            "or use LinkedIn export ZIP instead."
        )
    return msg


@profile_bp.route("/api/profile/import-linkedin", methods=["POST"])
def import_linkedin():
    """Scrape the logged-in LinkedIn profile and extract profile fields."""
    body = request.get_json(silent=True) or {}
    llm_config, config = _resolve_llm_for_import(body)
    if not llm_config:
        return jsonify({"error": t("errors.ai_required_for_import")}), 400

    try:
        scraped = scrape_linkedin_profile()
        extracted = extract_profile_from_text(
            scraped["raw_text"],
            llm_config,
            source_label="LinkedIn Profile",
        )
        if scraped.get("profile_url") and not extracted.get("profile", {}).get("linkedin_url"):
            extracted.setdefault("profile", {})["linkedin_url"] = scraped["profile_url"]
    except Exception as e:
        logger.exception("LinkedIn import failed")
        return jsonify({"error": _linkedin_import_error_message(e)}), 500

    apply_now = body.get("apply", False)
    result = {"extracted": extracted, "source": "linkedin", "profile_url": scraped.get("profile_url")}
    if apply_now and config:
        result.update(_apply_import(extracted, config, "linkedin"))

    return jsonify(result)


@profile_bp.route("/api/profile/import-linkedin-zip", methods=["POST"])
def import_linkedin_zip():
    """Import profile from a LinkedIn data export ZIP file."""
    llm_config, config = _resolve_llm_for_import()
    if not llm_config:
        return jsonify({"error": t("errors.ai_required_for_import")}), 400

    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": t("errors.no_file_provided")}), 400

    if not f.filename.lower().endswith(".zip"):
        return jsonify({"error": t("errors.linkedin_zip_required")}), 400

    data = f.read()
    if len(data) > _MAX_ZIP_SIZE:
        return jsonify({"error": t("errors.file_too_large")}), 400

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        raw_text = parse_linkedin_export_zip(tmp_path)
        extracted = extract_profile_from_text(
            raw_text,
            llm_config,
            source_label="LinkedIn Export",
        )
    except Exception as e:
        logger.exception("LinkedIn ZIP import failed")
        return jsonify({"error": str(e)}), 500
    finally:
        tmp_path.unlink(missing_ok=True)

    apply_now = request.args.get("apply", "").lower() in ("1", "true", "yes")
    result = {"extracted": extracted, "source": "linkedin_zip"}
    if apply_now and config:
        result.update(_apply_import(extracted, config, "linkedin"))

    return jsonify(result)


@profile_bp.route("/api/profile/apply-import", methods=["POST"])
def apply_profile_import():
    """Apply previously extracted profile data to config."""
    config = load_config()
    if config is None:
        return jsonify({"error": t("errors.invalid_config", count=1)}), 400

    data = request.get_json(force=True) or {}
    extracted = data.get("extracted")
    if not extracted:
        return jsonify({"error": t("errors.extracted_data_required")}), 400

    source = data.get("source", "import")
    result = _apply_import(extracted, config, source)
    return jsonify({"success": True, **result})
