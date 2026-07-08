"""Platform login browser routes.

Implements: FR-068 (platform login browser).
"""

from __future__ import annotations

import logging
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
from config.settings import get_data_dir  # Backward compatibility for tests.
from core.browser_engine import (
    engine_display_name,
    find_system_chrome,
    launch_persistent_context,
    preferred_engine,
    profile_dir as engine_profile_dir,
    read_platform_sessions,
)
from core.i18n import t

logger = logging.getLogger(__name__)

login_bp = Blueprint("login", __name__)

INDEED_SESSION_COOKIES = frozenset({"INDEED_CSRF_TOKEN", "indeed_rcc"})


def _profile_dir() -> Path:
    return engine_profile_dir(app_state.login_engine or preferred_engine())


def _get_cdp_port(profile: Path) -> int | None:
    """Return the Chrome DevTools port for the login profile, if available."""
    port_file = profile / "DevToolsActivePort"
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


def _profile_chrome_running(profile: Path) -> bool:
    """Return True if any Chrome process is using the login profile directory."""
    marker = str(profile)
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


def _playwright_login_alive() -> bool:
    """Return True if a Playwright-managed login browser is still open."""
    context = app_state.login_context
    if context is None:
        return False
    try:
        return bool(context.pages)
    except Exception:
        app_state.login_context = None
        app_state.login_playwright = None
        return False


def _login_browser_alive() -> bool:
    """Return True if the dedicated login browser is still running."""
    if _playwright_login_alive():
        return True

    profile = _profile_dir()
    port = _get_cdp_port(profile)
    if port and _cdp_reachable(port):
        return True

    if _profile_chrome_running(profile):
        return True

    if app_state.login_proc is None:
        return False
    if app_state.login_proc.poll() is not None:
        app_state.login_proc = None
        return False
    return True


def _close_playwright_login() -> None:
    """Close a Playwright-managed login browser."""
    if app_state.login_context is not None:
        try:
            app_state.login_context.close()
        except Exception as e:
            logger.debug("Failed to close Playwright login context: %s", e)
        app_state.login_context = None

    if app_state.login_playwright is not None:
        try:
            app_state.login_playwright.stop()
        except Exception as e:
            logger.debug("Failed to stop Playwright login instance: %s", e)
        app_state.login_playwright = None


def _prepare_fresh_login_browser(profile: Path) -> None:
    """Ensure a login browser can start for the active profile."""
    if _playwright_login_alive():
        return

    port = _get_cdp_port(profile)
    if port and _cdp_reachable(port):
        return
    if _profile_chrome_running(profile) or app_state.login_proc is not None:
        logger.info("Closing stale login browser before opening a fresh session")
        _close_profile_browser(profile)
        app_state.login_proc = None
        time.sleep(0.5)


def _chrome_login_args(chrome_path: str, profile: str, url: str) -> list[str]:
    """Build Chrome args for the dedicated login profile (no --new-window)."""
    return [
        chrome_path,
        f"--user-data-dir={profile}",
        "--remote-debugging-port=0",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-default-apps",
        url,
    ]


def _sessions_from_cookies_file(profile: Path) -> dict[str, bool]:
    """Read platform session cookies from the on-disk Chrome Cookies DB."""
    profile_cookies = profile / "Default" / "Network" / "Cookies"
    result = {"linkedin": False, "indeed": False}
    if not profile_cookies.exists():
        return result

    tmp_cookies = profile / "_cookies_check.db"
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


def _sessions_via_cdp(profile: Path) -> dict[str, bool] | None:
    """Read platform session cookies from a running login Chrome via CDP."""
    port = _get_cdp_port(profile)
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


def _kill_chrome_with_profile(profile: str) -> None:
    """Force-close Chrome processes bound to the login profile directory."""
    marker = profile.replace("'", "''")
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
        else:
            subprocess.run(
                ["pkill", "-f", profile],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    except Exception as e:
        logger.debug("Failed to kill profile Chrome processes: %s", e)


def _close_profile_browser(profile: Path) -> None:
    """Close the dedicated login browser instance."""
    _close_playwright_login()

    port = _get_cdp_port(profile)
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

    _kill_chrome_with_profile(str(profile))


def _open_chrome_login(url: str, profile: Path) -> str:
    """Open system Chrome for platform login. Returns status string."""
    chrome_path = find_system_chrome()
    if not chrome_path:
        raise RuntimeError(t("errors.chrome_not_found"))

    chrome_args = _chrome_login_args(chrome_path, str(profile), url)
    reuse = _login_browser_alive() and _get_cdp_port(profile) is not None

    if not reuse:
        _prepare_fresh_login_browser(profile)

    proc = subprocess.Popen(
        chrome_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if reuse:
        logger.info("Login browser navigated in existing Chrome session: %s", url)
        return "navigated"

    app_state.login_proc = proc
    app_state.login_engine = "chromium"
    logger.info("Login browser opened (Chrome PID %d): %s", proc.pid, url)
    return "opening"


def _open_playwright_login(url: str, engine: str) -> str:
    """Open a Playwright browser for platform login. Returns status string."""
    from playwright.sync_api import sync_playwright

    if _playwright_login_alive():
        pages = app_state.login_context.pages
        page = pages[0] if pages else app_state.login_context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        logger.info("Login browser navigated in existing session: %s", url)
        return "navigated"

    _prepare_fresh_login_browser(engine_profile_dir(engine))

    playwright = sync_playwright().start()
    context = launch_persistent_context(playwright, engine=engine, headless=False)
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    app_state.login_playwright = playwright
    app_state.login_context = context
    app_state.login_engine = engine
    logger.info(
        "Login browser opened (%s): %s",
        engine_display_name(engine),
        url,
    )
    return "opening"


@login_bp.route("/api/login/browser-info", methods=["GET"])
def login_browser_info():
    """Return which browser engine the app will use for login/automation."""
    engine = preferred_engine()
    return jsonify({
        "engine": engine,
        "display_name": engine_display_name(engine),
        "chrome_available": find_system_chrome() is not None,
    })


@login_bp.route("/api/login/open", methods=["POST"])
def login_open():
    """Open a browser with a dedicated profile for platform login."""
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

    engine = preferred_engine()

    with app_state.login_lock:
        try:
            if engine == "chromium" and find_system_chrome():
                status = _open_chrome_login(url, engine_profile_dir("chromium"))
            else:
                status = _open_playwright_login(url, "webkit")
        except Exception as e:
            logger.error("Failed to open login browser: %s", e)
            return jsonify({"error": t("errors.browser_failed", error=str(e))}), 500

    return jsonify({"status": status, "engine": app_state.login_engine})


@login_bp.route("/api/login/close", methods=["POST"])
def login_close():
    """Close the login browser."""
    with app_state.login_lock:
        if (
            not _login_browser_alive()
            and app_state.login_proc is None
            and app_state.login_context is None
        ):
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
    engine = app_state.login_engine or preferred_engine()
    profile = engine_profile_dir(engine)
    result = {"linkedin": False, "indeed": False}

    if app_state.login_context is not None:
        result = read_platform_sessions(engine, open_context=app_state.login_context)
    elif engine == "chromium":
        result = _sessions_from_cookies_file(profile)
        cdp_result = _sessions_via_cdp(profile)
        if cdp_result:
            result["linkedin"] = result["linkedin"] or cdp_result["linkedin"]
            result["indeed"] = result["indeed"] or cdp_result["indeed"]
    else:
        result = read_platform_sessions(engine)

    return jsonify(result)
