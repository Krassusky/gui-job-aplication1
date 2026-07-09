"""Lightweight REST API for sharing discovered jobs with Mac clients."""

from __future__ import annotations

import logging
import os
import threading

from flask import Flask, Response, jsonify, request

from config.settings import get_data_dir
from db.database import Database
from worker.hunter_dashboard_html import DASHBOARD_HTML
from worker.hunter_state import hunter_state

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


def _check_sync_auth() -> tuple[dict | None, int | None]:
    expected = _get_sync_token()
    if not expected:
        return {"error": "Sync token not configured on server"}, 503
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        return {"error": "Unauthorized"}, 401
    return None, None


def create_sync_app(db: Database | None = None) -> Flask:
    """Create the sync Flask application."""
    app = Flask(__name__)
    database = db or Database(get_data_dir() / "autoapply.db")

    @app.route("/", methods=["GET"])
    @app.route("/dashboard", methods=["GET"])
    def dashboard():
        return Response(DASHBOARD_HTML, mimetype="text/html; charset=utf-8")

    @app.route("/api/hunter/dashboard", methods=["GET"])
    def hunter_dashboard_api():
        stats = hunter_state.get_stats_dict()
        pending = database.get_sync_jobs(limit=50)
        stats["pending_sync"] = len(pending)
        return jsonify(
            {
                "stats": stats,
                "activity": hunter_state.get_events(limit=100),
                "pending_jobs": pending,
            }
        )

    @app.route("/api/sync/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

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
