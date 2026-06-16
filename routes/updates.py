"""Application update routes (GitHub Releases)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from core.i18n import t
from core.updater import (
    UpdateError,
    apply_update_and_restart,
    check_for_updates,
    get_app_version,
    get_update_state,
    is_updater_available,
    start_download,
)

updates_bp = Blueprint("updates", __name__)


@updates_bp.route("/api/updates/info", methods=["GET"])
def updates_info():
    return jsonify({
        "current_version": get_app_version(),
        "can_install": is_updater_available(),
    })


@updates_bp.route("/api/updates/check", methods=["POST"])
def updates_check():
    try:
        return jsonify(check_for_updates())
    except UpdateError as e:
        return jsonify({"error": str(e), **get_update_state()}), 502


@updates_bp.route("/api/updates/download", methods=["POST"])
def updates_download():
    if not is_updater_available():
        return jsonify({"error": t("updates.dev_mode")}), 400
    try:
        check = check_for_updates()
    except UpdateError as e:
        return jsonify({"error": str(e)}), 502
    if not check.get("update_available"):
        return jsonify({"error": t("updates.already_latest")}), 400
    if check.get("ready"):
        return jsonify(get_update_state())
    start_download()
    return jsonify(get_update_state())


@updates_bp.route("/api/updates/status", methods=["GET"])
def updates_status():
    return jsonify(get_update_state())


@updates_bp.route("/api/updates/install", methods=["POST"])
def updates_install():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify({"error": t("errors.forbidden")}), 403
    if not is_updater_available():
        return jsonify({"error": t("updates.dev_mode")}), 400
    try:
        apply_update_and_restart()
    except UpdateError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "installing"})
