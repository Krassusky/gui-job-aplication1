"""Application CRUD, export, cover letter, resume, and job description routes.

Implements: FR-007 (application CRUD), FR-008 (CSV export), FR-065 (application detail).
"""

from __future__ import annotations

import io
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

import app_state
from config.settings import get_data_dir
from core.i18n import t

applications_bp = Blueprint("applications", __name__)


def _is_safe_path(file_path: str | Path) -> bool:
    """Verify file_path is within the autoapply data directory (no traversal)."""
    try:
        resolved = Path(file_path).resolve()
        allowed = get_data_dir().resolve()
        return resolved.is_relative_to(allowed) and resolved.exists()
    except (ValueError, OSError):
        return False


def _get_db():
    """Return the database instance or abort 503 if not initialized."""
    db = app_state.db
    if db is None:
        from flask import abort
        abort(503, description="Database not initialized")
    return db


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@applications_bp.route("/api/applications", methods=["GET"])
def get_applications():
    """List applications with pagination.

    Prefers ``page`` / ``per_page`` (frontend contract). Also accepts legacy
    ``limit`` / ``offset``. Always returns ``{applications, total, page, per_page}``.
    """
    status = request.args.get("status")
    platform_filter = request.args.get("platform")
    search = request.args.get("search")

    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)
    if page is not None or per_page is not None:
        page = max(1, page or 1)
        per_page = min(100, max(1, per_page or 15))
        limit = per_page
        offset = (page - 1) * per_page
    else:
        limit = min(100, max(1, request.args.get("limit", 50, type=int)))
        offset = max(0, request.args.get("offset", 0, type=int))
        page = (offset // limit) + 1 if limit else 1
        per_page = limit

    db = _get_db()
    applications = db.get_all_applications(
        status=status,
        platform=platform_filter,
        search=search,
        limit=limit,
        offset=offset,
    )
    total = db.count_applications(
        status=status,
        platform=platform_filter,
        search=search,
    )
    return jsonify({
        "applications": [a.model_dump() for a in applications],
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@applications_bp.route("/api/applications/<int:app_id>", methods=["GET"])
def get_application_detail(app_id: int):
    application = _get_db().get_application(app_id)
    if not application:
        return jsonify({"error": t("errors.application_not_found")}), 404
    return jsonify(application.model_dump())


@applications_bp.route("/api/applications/<int:app_id>/events", methods=["GET"])
def get_application_events(app_id: int):
    application = _get_db().get_application(app_id)
    if not application:
        return jsonify({"error": t("errors.application_not_found")}), 404
    events = _get_db().get_feed_events_for_job(application.job_title, application.company)
    return jsonify([e.model_dump() for e in events])


@applications_bp.route("/api/applications/export", methods=["GET"])
def export_applications():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    tmp.close()
    csv_path = Path(tmp.name)
    try:
        _get_db().export_csv(csv_path)
        data = csv_path.read_bytes()
    finally:
        csv_path.unlink(missing_ok=True)

    buf = io.BytesIO(data)
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"applications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    )


@applications_bp.route("/api/applications/<int:app_id>", methods=["PATCH"])
def update_application(app_id: int):
    data = request.get_json()
    if not data:
        return jsonify({"error": t("errors.request_body_required")}), 400
    application = _get_db().get_application(app_id)
    if not application:
        return jsonify({"error": t("errors.application_not_found")}), 404
    status = data.get("status", application.status)
    if status not in app_state.VALID_APP_STATUSES:
        return jsonify({"error": t("errors.invalid_status", valid_statuses=", ".join(sorted(app_state.VALID_APP_STATUSES)))}), 400
    notes = data.get("notes", application.notes)
    _get_db().update_status(app_id, status=status, notes=notes)
    return jsonify({"success": True})


@applications_bp.route("/api/applications/<int:app_id>/cover_letter", methods=["GET"])
def get_cover_letter(app_id: int):
    application = _get_db().get_application(app_id)
    if not application:
        return jsonify({"error": t("errors.application_not_found")}), 404
    return jsonify({
        "cover_letter_text": application.cover_letter_text,
        "file_path": application.cover_letter_path,
    })


@applications_bp.route("/api/applications/<int:app_id>/resume", methods=["GET"])
def get_resume(app_id: int):
    application = _get_db().get_application(app_id)
    if not application:
        return jsonify({"error": t("errors.application_not_found")}), 404
    resume_path = application.resume_path
    if not resume_path or not _is_safe_path(resume_path):
        return jsonify({"error": t("errors.resume_not_found")}), 404
    return send_file(resume_path, mimetype="application/pdf")


@applications_bp.route("/api/applications/<int:app_id>/description", methods=["GET"])
def get_job_description(app_id: int):
    application = _get_db().get_application(app_id)
    if not application:
        return jsonify({"error": t("errors.application_not_found")}), 404
    desc_path = application.description_path
    if desc_path and _is_safe_path(desc_path):
        return send_file(desc_path, mimetype="text/html")
    # Imported sync jobs often store JD as description_text only
    text = (application.description_text or "").strip()
    if not text:
        return jsonify({"error": t("errors.description_not_found")}), 404
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{application.job_title}</title></head><body>"
        f"<h1>{application.job_title}</h1>"
        f"<p><strong>{application.company}</strong></p>"
        f"<pre style='white-space:pre-wrap;font-family:system-ui,sans-serif'>"
        f"{text}</pre></body></html>"
    )
    buf = io.BytesIO(html.encode("utf-8"))
    return send_file(buf, mimetype="text/html")


@applications_bp.route("/api/applications/<int:app_id>/generate", methods=["POST"])
def generate_application_materials(app_id: int):
    """Generate adaptive resume + cover letter for an existing application."""
    from bot.bot import generate_for_application

    db = _get_db()
    application = db.get_application(app_id)
    if not application:
        return jsonify({"error": t("errors.application_not_found")}), 404

    from config.settings import load_config
    config = load_config()
    if config is None:
        return jsonify({"error": t("errors.config_not_found")}), 400

    try:
        result = generate_for_application(app_id, config, db)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


@applications_bp.route("/api/applications/<int:app_id>/apply", methods=["POST"])
def apply_to_application(app_id: int):
    """Start apply pipeline for one imported/discovered application (reuses bot appliers + review)."""
    from routes.bot import start_apply_one

    db = _get_db()
    application = db.get_application(app_id)
    if not application:
        return jsonify({"error": t("errors.application_not_found")}), 404
    if not (application.apply_url or "").strip():
        return jsonify({"error": t("errors.apply_url_required")}), 400

    result = start_apply_one(app_id)
    if result == "already_running":
        return jsonify({"error": t("errors.bot_already_running")}), 409
    if result == "no_config":
        return jsonify({"error": t("errors.config_not_found")}), 400
    return jsonify({"status": "started", "application_id": app_id})
