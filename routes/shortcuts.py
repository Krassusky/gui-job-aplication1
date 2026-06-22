"""Desktop shortcut routes for packaged builds."""

from __future__ import annotations

from flask import Blueprint, jsonify

from core.i18n import t
from core.shortcuts import (
    ShortcutError,
    get_shortcuts_status,
    install_shortcuts,
    is_shortcuts_available,
    mark_shortcuts_declined,
)

shortcuts_bp = Blueprint("shortcuts", __name__)


@shortcuts_bp.route("/api/shortcuts/status", methods=["GET"])
def shortcuts_status():
    return jsonify(get_shortcuts_status())


@shortcuts_bp.route("/api/shortcuts/install", methods=["POST"])
def shortcuts_install():
    if not is_shortcuts_available():
        return jsonify({"error": t("shortcuts.dev_mode")}), 400
    try:
        return jsonify(install_shortcuts())
    except ShortcutError as e:
        return jsonify({"error": str(e)}), 500


@shortcuts_bp.route("/api/shortcuts/decline", methods=["POST"])
def shortcuts_decline():
    if not is_shortcuts_available():
        return jsonify({"error": t("shortcuts.dev_mode")}), 400
    mark_shortcuts_declined()
    return jsonify({"success": True, **get_shortcuts_status()})
