"""Platform login browser routes.

Implements: FR-068 (platform login browser).
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request

import app_state
from config.settings import get_data_dir
from core.i18n import t

logger = logging.getLogger(__name__)

login_bp = Blueprint("login", __name__)

INDEED_SESSION_COOKIES = frozenset({"INDEED_CSRF_TOKEN", "indeed_rcc"})


def _profile_dir() -> Path:
    return get_data_dir() / "browser_profile"


def _get_cdp_port(profile_dir: Path) -> int | None:
    """Return the Chrome DevTools port for the login profile, if available."""
    port_file = profile_dir / "DevToolsActivePort"
    if not port_file.exists():
        return None
    try:
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0].strip())
        return port if port > 0 else None
    except (OSError, ValueError, IndexError):
        return None


def _cdp_reachable(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version",
            timeout=1,
        ) as resp:
            return bool(resp.status == 200)
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _profile_chrome_running(profile_dir: Path) -> bool:
    """Return True if any Chrome process is using the login profile directory."""
    marker = str(profile_dir)
    system = platform.system()
    try:
        if system == "Windows":
            ps_cmd = (
                "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
                f"Where-Object {{ $_.CommandLine -like '*{marker.replace(chr(39), chr(39)+chr(39))}*' }} | "
                "Select-Object -First 1 -ExpandProperty ProcessId"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            return bool(result.stdout.strip())
        result = subprocess.run(
            ["pgrep", "-f", marker],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.returncode == 0
    except Exception as e:
        logger.debug("Could not detect profile Chrome processes: %s", e)
        return False


def _login_browser_alive() -> bool:
    """Return True if the dedicated login Chrome profile is still running."""
    profile_dir = _profile_dir()
    port = _get_cdp_port(profile_dir)
    if port and _cdp_reachable(port):
        return True

    if _profile_chrome_running(profile_dir):
        return True

    if app_state.login_proc is None:
        return False
    if app_state.login_proc.poll() is not None:
        app_state.login_proc = None
        return False
    return True


def _prepare_fresh_login_browser(profile_dir: Path) -> None:
    """Ensure a CDP-enabled Chrome can start for the login profile."""
    port = _get_cdp_port(profile_dir)
    if port and _cdp_reachable(port):
        return
    if _profile_chrome_running(profile_dir) or app_state.login_proc is not None:
        logger.info("Closing stale login Chrome before opening a fresh session")
        _close_profile_browser(profile_dir)
        app_state.login_proc = None
        time.sleep(0.5)


def _chrome_login_args(chrome_path: str, profile_dir: str, url: str) -> list[str]:
    """Build Chrome args for the dedicated login profile (no --new-window).

    On Windows, launching Chrome with the same --user-data-dir attaches to an
    existing instance and opens the URL in a new tab instead of spawning a window.
    """
    return [
        chrome_path,
        f"--user-data-dir={profile_dir}",
        "--remote-debugging-port=0",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-default-apps",
        url,
    ]


def _find_system_chrome() -> str | None:
    """Find system-installed Chrome/Chromium for faster browser sessions."""
    candidates = []
    if platform.system() == "Windows":
        for base in [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.path.expandvars(r"%LOCALAPPDATA%"),
        ]:
            candidates.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    elif platform.system() == "Darwin":
        candidates.append("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    else:
        candidates.extend(["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"])

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _sessions_from_cookies_file(profile_dir: Path) -> dict[str, bool]:
    """Read platform session cookies from the on-disk Chrome Cookies DB."""
    profile_cookies = profile_dir / "Default" / "Network" / "Cookies"
    result = {"linkedin": False, "indeed": False}
    if not profile_cookies.exists():
        return result

    tmp_cookies = profile_dir / "_cookies_check.db"
    try:
        shutil.copy2(str(profile_cookies), str(tmp_cookies))
        conn = sqlite3.connect(str(tmp_cookies))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%linkedin.com' "
            "AND name = 'li_at'"
        )
        result["linkedin"] = cursor.fetchone()[0] > 0

        cursor.execute(
            "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%indeed.com' "
            "AND name IN ('INDEED_CSRF_TOKEN', 'indeed_rcc')"
        )
        result["indeed"] = cursor.fetchone()[0] > 0

        conn.close()
    except Exception as e:
        logger.debug("Could not read cookies DB: %s", e)
    finally:
        try:
            tmp_cookies.unlink(missing_ok=True)
        except OSError as e:
            logger.debug("Failed to clean up temp cookies file: %s", e)

    return result


def _sessions_via_cdp(profile_dir: Path) -> dict[str, bool] | None:
    """Read platform session cookies from a running login Chrome via CDP."""
    port = _get_cdp_port(profile_dir)
    if not port or not _cdp_reachable(port):
        return None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug("Playwright unavailable for CDP session check")
        return None

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            contexts = browser.contexts
            if not contexts:
                return {"linkedin": False, "indeed": False}

            cookies = contexts[0].cookies()
            linkedin = any(
                cookie.get("name") == "li_at" and "linkedin" in cookie.get("domain", "")
                for cookie in cookies
            )
            indeed = any(
                cookie.get("name") in INDEED_SESSION_COOKIES
                and "indeed" in cookie.get("domain", "")
                for cookie in cookies
            )
            return {"linkedin": linkedin, "indeed": indeed}
    except Exception as e:
        logger.debug("CDP session check failed: %s", e)
        return None


def _kill_chrome_with_profile(profile_dir: str) -> None:
    """Force-close Chrome processes bound to the login profile directory."""
    marker = profile_dir.replace("'", "''")
    system = platform.system()
    try:
        if system == "Windows":
            ps_cmd = (
                "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
                f"Where-Object {{ $_.CommandLine -like '*{marker}*' }} | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        elif system == "Darwin":
            subprocess.run(
                ["pkill", "-f", profile_dir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            subprocess.run(
                ["pkill", "-f", profile_dir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    except Exception as e:
        logger.debug("Failed to kill profile Chrome processes: %s", e)


def _close_profile_browser(profile_dir: Path) -> None:
    """Close the dedicated login Chrome instance."""
    port = _get_cdp_port(profile_dir)
    if port and _cdp_reachable(port):
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                browser.close()
            return
        except Exception as e:
            logger.debug("CDP browser close failed: %s", e)

    if app_state.login_proc is not None:
        try:
            app_state.login_proc.terminate()
        except OSError as e:
            logger.debug("Failed to terminate login launcher: %s", e)

    _kill_chrome_with_profile(str(profile_dir))


@login_bp.route("/api/login/open", methods=["POST"])
def login_open():
    """Open system Chrome with a dedicated profile for platform login."""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": t("errors.url_required")}), 400

    url = data["url"]
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception:
        return jsonify({"error": t("errors.invalid_url")}), 400
    allowed_domains = {"linkedin.com", "indeed.com"}
    if not any(host == d or host.endswith("." + d) for d in allowed_domains):
        return jsonify({"error": t("errors.unsupported_login_url")}), 400

    chrome_path = _find_system_chrome()
    if not chrome_path:
        return jsonify({
            "error": t("errors.chrome_not_found"),
        }), 500

    profile_dir = str(_profile_dir())
    chrome_args = _chrome_login_args(chrome_path, profile_dir, url)

    with app_state.login_lock:
        reuse = _login_browser_alive() and _get_cdp_port(_profile_dir()) is not None

        if not reuse:
            _prepare_fresh_login_browser(_profile_dir())

        try:
            proc = subprocess.Popen(
                chrome_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if reuse:
                logger.info(
                    "Login browser navigated in existing session: %s", url,
                )
            else:
                app_state.login_proc = proc
                logger.info(
                    "Login browser opened (Chrome PID %d): %s", proc.pid, url,
                )
        except Exception as e:
            logger.error("Failed to open login browser: %s", e)
            return jsonify({"error": t("errors.chrome_failed", error=str(e))}), 500

    status = "navigated" if reuse else "opening"
    return jsonify({"status": status})


@login_bp.route("/api/login/close", methods=["POST"])
def login_close():
    """Close the login browser."""
    with app_state.login_lock:
        if not _login_browser_alive() and app_state.login_proc is None:
            return jsonify({"status": "already_closed"})

        _close_profile_browser(_profile_dir())
        app_state.login_proc = None

    return jsonify({"status": "closed"})


@login_bp.route("/api/login/status", methods=["GET"])
def login_status():
    """Check if a login browser is currently open."""
    with app_state.login_lock:
        return jsonify({"open": _login_browser_alive()})


@login_bp.route("/api/login/sessions", methods=["GET"])
def login_sessions():
    """Check which platforms have active login sessions."""
    profile_dir = _profile_dir()
    result = _sessions_from_cookies_file(profile_dir)

    cdp_result = _sessions_via_cdp(profile_dir)
    if cdp_result:
        result["linkedin"] = result["linkedin"] or cdp_result["linkedin"]
        result["indeed"] = result["indeed"] or cdp_result["indeed"]

    return jsonify(result)
