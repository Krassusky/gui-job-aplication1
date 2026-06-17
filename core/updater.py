"""In-app update checker and installer (GitHub Releases)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from typing import Any, cast

import requests

from config.settings import get_data_dir
from core.version_info import get_app_version, is_newer_version, normalize_tag

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_REPO = "Krassusky/gui-job-aplication1"
GITHUB_API = "https://api.github.com"
EXE_NAME = "JobApplyAssistant.exe"

_lock = threading.Lock()
_state: dict[str, Any] = {
    "status": "idle",
    "progress": 0,
    "message": "",
    "current_version": "",
    "latest_version": "",
    "release_notes": "",
    "download_size": 0,
    "ready": False,
    "error": "",
    "can_install": False,
}


class UpdateError(Exception):
    pass


def get_update_state() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def _set_state(**kwargs: Any) -> None:
    with _lock:
        _state.update(kwargs)


def get_github_repo() -> str:
    return os.environ.get("AUTOAPPLY_UPDATE_REPO", DEFAULT_GITHUB_REPO).strip()


def get_platform_asset_suffix() -> str:
    if sys.platform == "win32":
        return "win-x64"
    if sys.platform == "darwin":
        return "mac-x64"
    return "linux-x64"


def get_install_dir() -> Path | None:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


def is_updater_available() -> bool:
    return get_install_dir() is not None and sys.platform == "win32"


def check_for_updates() -> dict[str, Any]:
    """Query GitHub for the latest release and compare versions."""
    current = get_app_version()
    _set_state(
        status="checking",
        progress=0,
        message="",
        error="",
        current_version=current,
        ready=False,
        can_install=is_updater_available(),
    )

    try:
        release = _fetch_latest_release()
    except UpdateError as e:
        _set_state(status="error", error=str(e))
        raise

    latest = normalize_tag(release.get("tag_name", ""))
    notes = release.get("body") or ""
    asset = _pick_release_asset(release.get("assets") or [])
    update_available = bool(latest) and is_newer_version(latest, current)

    payload = {
        "status": "idle",
        "current_version": current,
        "latest_version": latest,
        "update_available": update_available,
        "release_notes": notes,
        "download_size": asset.get("size", 0) if asset else 0,
        "asset_name": asset.get("name") if asset else None,
        "can_install": is_updater_available(),
        "ready": _is_download_ready(latest),
    }
    _set_state(
        status="idle",
        current_version=current,
        latest_version=latest,
        release_notes=notes,
        download_size=payload["download_size"],
        ready=payload["ready"],
        error="",
    )
    return payload


def start_download() -> None:
    """Download the latest release asset in a background thread."""
    if _state.get("status") == "downloading":
        return

    def _run():
        try:
            _download_latest()
        except Exception as e:
            logger.exception("Update download failed")
            _set_state(status="error", error=str(e), progress=0)

    threading.Thread(target=_run, daemon=True, name="update-download").start()


def apply_update_and_restart() -> None:
    """Launch a helper script to replace files and restart (Windows only)."""
    install_dir = get_install_dir()
    if install_dir is None:
        raise UpdateError("Updates can only be installed from the packaged app.")

    latest = _state.get("latest_version") or ""
    extract_dir = _extract_dir_for(latest)
    if not extract_dir.is_dir():
        raise UpdateError("Download the update before installing.")

    source_dir = _find_package_root(extract_dir)
    if not (source_dir / EXE_NAME).is_file():
        raise UpdateError("Update package is missing the application executable.")

    if sys.platform != "win32":
        raise UpdateError("Automatic install is supported on Windows only.")

    bat_path = _write_windows_updater(install_dir, source_dir)
    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
    _set_state(status="installing", message="Restarting...")


def _updates_dir() -> Path:
    path = get_data_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _zip_path_for(version: str) -> Path:
    return _updates_dir() / f"JobApplyAssistant-{version}.zip"


def _extract_dir_for(version: str) -> Path:
    return _updates_dir() / f"extract-{version}"


def _is_download_ready(version: str) -> bool:
    if not version:
        return False
    extract_dir = _extract_dir_for(version)
    if not extract_dir.is_dir():
        return False
    try:
        _find_package_root(extract_dir)
        return True
    except UpdateError:
        return False


def _fetch_latest_release() -> dict[str, Any]:
    repo = get_github_repo()
    url = f"{GITHUB_API}/repos/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "JobApplyAssistant-Updater"}
    try:
        resp = requests.get(url, timeout=20, headers=headers)
    except requests.RequestException as e:
        raise UpdateError(f"Could not reach GitHub: {e}") from e

    if resp.status_code == 404:
        raise UpdateError("No releases found on GitHub yet.")
    if resp.status_code != 200:
        raise UpdateError(f"GitHub returned status {resp.status_code}.")

    return cast(dict[str, Any], resp.json())


def _pick_release_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    suffix = get_platform_asset_suffix().lower()
    zips = [a for a in assets if (a.get("name") or "").lower().endswith(".zip")]
    for asset in zips:
        if suffix in (asset.get("name") or "").lower():
            return asset
    for asset in zips:
        if "jobapplyassistant" in (asset.get("name") or "").lower():
            return asset
    return zips[0] if zips else None


def _download_latest() -> None:
    release = _fetch_latest_release()
    latest = normalize_tag(release.get("tag_name", ""))
    asset = _pick_release_asset(release.get("assets") or [])
    if not asset or not asset.get("browser_download_url"):
        raise UpdateError(f"No {get_platform_asset_suffix()} download found in the latest release.")

    url = asset["browser_download_url"]
    total = int(asset.get("size") or 0)
    zip_path = _zip_path_for(latest)
    extract_dir = _extract_dir_for(latest)

    _set_state(
        status="downloading",
        progress=0,
        message="Downloading...",
        error="",
        latest_version=latest,
        release_notes=release.get("body") or "",
        download_size=total,
        ready=False,
    )

    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)

    downloaded = 0
    headers = {"User-Agent": "JobApplyAssistant-Updater"}
    with requests.get(url, stream=True, timeout=60, headers=headers) as resp:
        resp.raise_for_status()
        if not total:
            total = int(resp.headers.get("Content-Length") or 0)
        with open(zip_path, "wb") as out:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                out.write(chunk)
                downloaded += len(chunk)
                if total:
                    _set_state(progress=min(99, int(downloaded * 100 / total)))

    _extract_zip(zip_path, extract_dir)
    _find_package_root(extract_dir)

    _set_state(status="ready", progress=100, message="Update ready to install.", ready=True)


def _extract_zip(zip_path: Path, extract_dir: Path) -> None:
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)


def _find_package_root(extract_dir: Path) -> Path:
    if not extract_dir.is_dir():
        raise UpdateError("Update files not found.")
    if (extract_dir / EXE_NAME).is_file():
        return extract_dir
    for child in extract_dir.iterdir():
        if child.is_dir() and (child / EXE_NAME).is_file():
            return child
    for exe in extract_dir.rglob(EXE_NAME):
        return exe.parent
    raise UpdateError("Could not find JobApplyAssistant.exe in the update package.")


def _write_windows_updater(install_dir: Path, source_dir: Path) -> Path:
    bat_path = _updates_dir() / "apply_update.bat"
    exe_path = install_dir / EXE_NAME
    content = f"""@echo off
setlocal EnableExtensions
echo Updating JobApply Assistant...
timeout /t 2 /nobreak >nul
xcopy /E /Y /I "{source_dir}\\*" "{install_dir}\\" >nul
if exist "{exe_path}" (
  start "" "{exe_path}"
)
del /F /Q "%~f0" >nul 2>&1
"""
    bat_path.write_text(content, encoding="utf-8")
    return bat_path
