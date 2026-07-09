"""Mac client routes for importing jobs from a remote Job Hunter server."""

from __future__ import annotations

import logging

import requests
from flask import Blueprint, jsonify, request

from config.settings import SyncConfig, get_data_dir, load_config, save_config
from core.i18n import t
from db.database import Database

logger = logging.getLogger(__name__)

sync_bp = Blueprint("sync", __name__)


def _get_db() -> Database:
    return Database(get_data_dir() / "autoapply.db")


def _sync_settings() -> SyncConfig:
    config = load_config()
    if config is None:
        return SyncConfig()
    return config.sync


def _save_sync_settings(sync: SyncConfig) -> None:
    config = load_config()
    if config is None:
        return
    config.sync = sync
    save_config(config)


def _normalize_server_url(url: str) -> str:
    return url.strip().rstrip("/")


def _fetch_remote_jobs(server_url: str, token: str, since: str | None = None) -> list[dict]:
    params = {}
    if since:
        params["since"] = since
    resp = requests.get(
        f"{server_url}/api/sync/jobs",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("jobs", [])


def _fetch_remote_job_detail(server_url: str, token: str, job_id: int) -> dict:
    resp = requests.get(
        f"{server_url}/api/sync/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _ack_remote_job(server_url: str, token: str, job_id: int) -> None:
    resp = requests.post(
        f"{server_url}/api/sync/jobs/{job_id}/ack",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()


@sync_bp.route("/api/sync/settings", methods=["GET"])
def get_sync_settings():
    sync = _sync_settings()
    return jsonify({
        "sync_server_url": sync.sync_server_url,
        "sync_token_configured": bool(sync.sync_token),
    })


@sync_bp.route("/api/sync/settings", methods=["PUT"])
def update_sync_settings():
    data = request.get_json() or {}
    sync = _sync_settings()
    if "sync_server_url" in data:
        sync.sync_server_url = str(data["sync_server_url"]).strip()
    if "sync_token" in data:
        sync.sync_token = str(data["sync_token"]).strip()
    _save_sync_settings(sync)
    return jsonify({"success": True})


@sync_bp.route("/api/sync/test", methods=["POST"])
def test_sync_connection():
    sync = _sync_settings()
    server_url = _normalize_server_url(sync.sync_server_url)
    if not server_url or not sync.sync_token:
        return jsonify({"error": t("errors.sync_not_configured")}), 400
    try:
        resp = requests.get(
            f"{server_url}/api/sync/health",
            timeout=10,
        )
        resp.raise_for_status()
        return jsonify({"success": True, "status": resp.json().get("status", "ok")})
    except requests.RequestException as e:
        logger.warning("Sync connection test failed: %s", e)
        return jsonify({"error": str(e)}), 502


@sync_bp.route("/api/sync/import", methods=["POST"])
def import_jobs():
    """Fetch pending jobs from the home server and import into local DB."""
    sync = _sync_settings()
    server_url = _normalize_server_url(sync.sync_server_url)
    if not server_url or not sync.sync_token:
        return jsonify({"error": t("errors.sync_not_configured")}), 400

    data = request.get_json(silent=True) or {}
    since = data.get("since")

    db = _get_db()
    imported = 0
    skipped = 0
    errors: list[str] = []

    try:
        jobs = _fetch_remote_jobs(server_url, sync.sync_token, since=since)
    except requests.RequestException as e:
        logger.error("Failed to fetch remote jobs: %s", e)
        return jsonify({"error": str(e)}), 502

    for summary in jobs:
        job_id = summary.get("id")
        external_id = summary.get("external_id", "")
        platform = summary.get("platform", "")
        if not job_id or not external_id or not platform:
            errors.append(f"Invalid job summary: {summary}")
            continue

        if db.exists(external_id, platform):
            skipped += 1
            try:
                _ack_remote_job(server_url, sync.sync_token, int(job_id))
            except requests.RequestException as e:
                logger.warning("Failed to ack duplicate job %s: %s", job_id, e)
            continue

        try:
            detail = _fetch_remote_job_detail(server_url, sync.sync_token, int(job_id))
        except requests.RequestException as e:
            errors.append(f"Job {job_id}: {e}")
            continue

        description_text = detail.get("description_text") or ""
        local_id = db.save_application(
            external_id=detail.get("external_id", external_id),
            platform=detail.get("platform", platform),
            job_title=detail.get("job_title", ""),
            company=detail.get("company", ""),
            location=detail.get("location"),
            salary=detail.get("salary"),
            apply_url=detail.get("apply_url", ""),
            match_score=int(detail.get("match_score") or 0),
            resume_path=None,
            cover_letter_path=None,
            cover_letter_text=None,
            status="discovered",
            error_message=None,
            description_text=description_text or None,
        )
        if local_id:
            imported += 1
            try:
                _ack_remote_job(server_url, sync.sync_token, int(job_id))
            except requests.RequestException as e:
                errors.append(f"Imported {local_id} but ack failed: {e}")

    return jsonify({
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    })
