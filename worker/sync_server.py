"""Lightweight REST API for sharing discovered jobs + shared config with Mac clients.

Sync API (Bearer AUTOAPPLY_SYNC_TOKEN):
  GET  /api/sync/health
  GET  /api/sync/jobs?since=<iso>
  GET  /api/sync/jobs/<id>
  POST /api/sync/jobs/<id>/ack
  GET  /api/sync/config          — shared profile + search_criteria + bot filters
  PUT  /api/sync/config          — update shared subset → ~/.autoapply/config.json

Hunter web UI (session cookie after login, or Bearer sync token):
  GET  /api/hunter/session
  POST /api/hunter/login
  POST /api/hunter/logout
  GET/PUT /api/hunter/config
  POST /api/hunter/start|stop
  GET  /api/hunter/dashboard|status
"""

from __future__ import annotations

import logging
import os
import threading

from flask import Flask, Response, jsonify, request, session

from config.settings import get_data_dir, load_config, save_config
from db.database import Database
from worker.hunter_auth import (
    SESSION_USER_KEY,
    credentials_configured,
    extract_shared_config,
    get_flask_secret,
    get_username,
    merge_shared_config,
    verify_password,
)
from worker.hunter_dashboard_html import DASHBOARD_HTML
from worker.hunter_state import hunter_state
from worker.thermal import read_sensors

logger = logging.getLogger(__name__)

SYNC_HOST = os.environ.get("AUTOAPPLY_SYNC_HOST", "127.0.0.1")
SYNC_PORT = int(os.environ.get("AUTOAPPLY_SYNC_PORT", "8765"))


def _get_sync_token() -> str:
    token = os.environ.get("AUTOAPPLY_SYNC_TOKEN", "").strip()
    if token:
        return token
    token_path = get_data_dir() / ".sync_token"
    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()
    return ""


def _is_localhost() -> bool:
    return request.remote_addr in ("127.0.0.1", "::1")


def _bearer_ok() -> bool:
    expected = _get_sync_token()
    if not expected:
        return False
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {expected}":
        return True
    if request.args.get("token") == expected:
        return True
    body = request.get_json(silent=True) or {}
    if body.get("token") == expected:
        return True
    return False


def _session_ok() -> bool:
    return bool(session.get(SESSION_USER_KEY))


def _check_sync_auth() -> tuple[dict | None, int | None]:
    expected = _get_sync_token()
    if not expected:
        return {"error": "Sync token not configured on server"}, 503
    if not _bearer_ok():
        return {"error": "Unauthorized"}, 401
    return None, None


def _check_web_auth() -> tuple[dict | None, int | None]:
    """Auth for hunter dashboard/control/config UI.

    Accepts session cookie or Bearer sync token. When neither hunter
    password nor sync token is configured, allow localhost only.
    """
    if _session_ok() or _bearer_ok():
        return None, None
    if not credentials_configured() and not _get_sync_token():
        if _is_localhost():
            return None, None
        return {"error": "Configure hunter login or AUTOAPPLY_SYNC_TOKEN"}, 503
    return {"error": "Unauthorized"}, 401


def _check_control_auth() -> tuple[dict | None, int | None]:
    """Auth for start/stop — same as web auth (no longer open on public URL)."""
    return _check_web_auth()


def create_sync_app(db: Database | None = None) -> Flask:
    """Create the sync Flask application."""
    app = Flask(__name__)
    app.secret_key = get_flask_secret()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    database = db or Database(get_data_dir() / "autoapply.db")

    @app.route("/", methods=["GET"])
    @app.route("/dashboard", methods=["GET"])
    def dashboard():
        return Response(DASHBOARD_HTML, mimetype="text/html; charset=utf-8")

    # ── Session / login ──────────────────────────────────────────────

    @app.route("/api/hunter/session", methods=["GET"])
    def hunter_session():
        authed = _session_ok() or _bearer_ok() or (
            not credentials_configured() and not _get_sync_token() and _is_localhost()
        )
        return jsonify(
            {
                "authenticated": bool(authed),
                "username": session.get(SESSION_USER_KEY) or (
                    get_username() if authed and credentials_configured() else None
                ),
                "auth_required": credentials_configured() or bool(_get_sync_token()),
                "credentials_configured": credentials_configured(),
            }
        )

    @app.route("/api/hunter/login", methods=["POST"])
    def hunter_login():
        data = request.get_json(silent=True) or {}
        # Allow signing in with the Mac sync Bearer token when no web password is set
        token = str(data.get("token") or "").strip()
        expected = _get_sync_token()
        if token and expected and token == expected:
            session[SESSION_USER_KEY] = "token"
            session.permanent = True
            return jsonify({"success": True, "username": "token"})

        if not credentials_configured():
            if expected:
                return jsonify(
                    {
                        "error": "Enter the sync token, or set AUTOAPPLY_HUNTER_PASSWORD "
                        "for username/password login"
                    }
                ), 401
            return jsonify(
                {
                    "error": "Hunter password not configured. "
                    "Set AUTOAPPLY_HUNTER_PASSWORD or ~/.autoapply/hunter_auth.json"
                }
            ), 503
        username = str(data.get("username") or "").strip()
        password = str(data.get("password") or "")
        if not verify_password(username, password):
            return jsonify({"error": "Invalid username or password"}), 401
        session[SESSION_USER_KEY] = username
        session.permanent = True
        return jsonify({"success": True, "username": username})

    @app.route("/api/hunter/logout", methods=["POST"])
    def hunter_logout():
        session.pop(SESSION_USER_KEY, None)
        return jsonify({"success": True})

    # ── Shared config (hunter UI) ────────────────────────────────────

    @app.route("/api/hunter/config", methods=["GET"])
    def hunter_get_config():
        err, code = _check_web_auth()
        if err:
            return jsonify(err), code
        config = load_config()
        return jsonify(extract_shared_config(config))

    @app.route("/api/hunter/config", methods=["PUT"])
    def hunter_put_config():
        err, code = _check_web_auth()
        if err:
            return jsonify(err), code
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON body required"}), 400
        config = load_config()
        if config is None:
            return jsonify({"error": "No config.json on hunter — create one first"}), 404
        try:
            merge_shared_config(config, payload)
            save_config(config)
        except Exception as e:
            logger.exception("Failed to save shared config")
            return jsonify({"error": str(e)}), 400
        return jsonify({"success": True, "config": extract_shared_config(config)})

    # ── Shared config (Mac sync API) ─────────────────────────────────

    @app.route("/api/sync/config", methods=["GET"])
    def sync_get_config():
        """Mac client pulls shared profile + search + bot filters."""
        err, code = _check_sync_auth()
        if err:
            return jsonify(err), code
        config = load_config()
        return jsonify(extract_shared_config(config))

    @app.route("/api/sync/config", methods=["PUT"])
    def sync_put_config():
        err, code = _check_sync_auth()
        if err:
            return jsonify(err), code
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON body required"}), 400
        config = load_config()
        if config is None:
            return jsonify({"error": "No config.json on hunter"}), 404
        try:
            merge_shared_config(config, payload)
            save_config(config)
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"success": True, "config": extract_shared_config(config)})

    # ── Dashboard / control ──────────────────────────────────────────

    @app.route("/api/hunter/dashboard", methods=["GET"])
    def hunter_dashboard_api():
        err, code = _check_web_auth()
        if err:
            return jsonify(err), code
        snap = read_sensors()
        hunter_state.update_sensors(snap.as_dict())
        stats = hunter_state.get_stats_dict()
        pending = database.get_sync_jobs(limit=50)
        stats["pending_sync"] = len(pending)
        return jsonify(
            {
                "stats": stats,
                "activity": hunter_state.get_events(limit=100),
                "pending_jobs": pending,
                "sensors": snap.as_dict(),
                "control_token_required": bool(_get_sync_token())
                and not _session_ok()
                and not _is_localhost(),
            }
        )

    @app.route("/api/hunter/status", methods=["GET"])
    def hunter_status():
        # Lightweight status — allow unauthenticated for health widgets;
        # omit sensitive pending job details.
        snap = read_sensors()
        hunter_state.update_sensors(snap.as_dict())
        stats = hunter_state.get_stats_dict()
        return jsonify(
            {
                "run_state": stats.get("run_state", "stopped"),
                "pause_reason": stats.get("pause_reason", ""),
                "sensors": snap.as_dict(),
                "want_running": hunter_state.want_running(),
            }
        )

    @app.route("/api/hunter/start", methods=["POST"])
    def hunter_start():
        err, code = _check_control_auth()
        if err:
            return jsonify(err), code
        result = hunter_state.request_start()
        status = 200 if result.get("ok") else 400
        return jsonify(result), status

    @app.route("/api/hunter/stop", methods=["POST"])
    def hunter_stop():
        err, code = _check_control_auth()
        if err:
            return jsonify(err), code
        result = hunter_state.request_stop()
        return jsonify(result)

    @app.route("/api/sync/health", methods=["GET"])
    def health():
        stats = hunter_state.get_stats_dict()
        return jsonify(
            {
                "status": "ok",
                "run_state": stats.get("run_state", "stopped"),
                "sensors": stats.get("sensors") or read_sensors().as_dict(),
            }
        )

    @app.route("/api/sync/jobs", methods=["GET"])
    def list_jobs():
        err, code = _check_sync_auth()
        if err:
            return jsonify(err), code
        since = request.args.get("since")
        jobs = database.get_sync_jobs(since=since)
        return jsonify({"jobs": jobs, "count": len(jobs)})

    @app.route("/api/sync/jobs/<int:job_id>", methods=["GET"])
    def job_detail(job_id: int):
        err, code = _check_sync_auth()
        if err:
            return jsonify(err), code
        job = database.get_sync_job(job_id)
        if job is None:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(job)

    @app.route("/api/sync/jobs/<int:job_id>/ack", methods=["POST"])
    def ack_job(job_id: int):
        err, code = _check_sync_auth()
        if err:
            return jsonify(err), code
        if not database.ack_sync_job(job_id):
            return jsonify({"error": "Job not found or already synced"}), 404
        return jsonify({"success": True, "id": job_id})

    return app


def run_sync_server(
    db: Database | None = None,
    host: str | None = None,
    port: int | None = None,
    threaded: bool = True,
) -> None:
    """Run the sync API (blocking)."""
    app = create_sync_app(db)
    bind_host = host or SYNC_HOST
    bind_port = port or SYNC_PORT
    logger.info("Starting sync API on %s:%s", bind_host, bind_port)
    app.run(host=bind_host, port=bind_port, threaded=threaded, use_reloader=False)


def start_sync_server_thread(
    db: Database | None = None,
    host: str | None = None,
    port: int | None = None,
) -> threading.Thread:
    """Start the sync API in a background daemon thread."""
    thread = threading.Thread(
        target=run_sync_server,
        kwargs={"db": db, "host": host, "port": port},
        name="sync-server",
        daemon=True,
    )
    thread.start()
    return thread
