"""Browser engine selection for automation and login flows.

On macOS we intentionally prefer WebKit (Safari engine) even when Chrome is
installed, because many users expect Safari-first behavior.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from config.settings import get_data_dir

logger = logging.getLogger(__name__)

BrowserEngine = Literal["chromium", "webkit"]
_checked_browser_installs: set[str] = set()


def find_system_chrome() -> str | None:
    """Return the path to system Google Chrome, if installed."""
    candidates: list[str] = []
    if platform.system() == "Windows":
        for base in [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.path.expandvars(r"%LOCALAPPDATA%"),
        ]:
            candidates.append(
                os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
            )
    elif platform.system() == "Darwin":
        candidates.append(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
    else:
        candidates.extend([
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ])

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def preferred_engine() -> BrowserEngine:
    """Pick the automation engine for this machine."""
    if platform.system() == "Darwin":
        return "webkit"
    if find_system_chrome():
        return "chromium"
    return "chromium"


def profile_dir(engine: BrowserEngine | None = None) -> Path:
    """Return the persistent browser profile directory for the given engine."""
    root = get_data_dir()
    if (engine or preferred_engine()) == "webkit":
        return root / "webkit_profile"
    return root / "browser_profile"


def engine_display_name(engine: BrowserEngine | None = None) -> str:
    """Human-readable browser name for UI messages."""
    resolved = engine or preferred_engine()
    if resolved == "webkit":
        return "Safari (WebKit)"
    if find_system_chrome():
        return "Google Chrome"
    return "Chromium"


def launch_persistent_context(
    playwright: Any,
    *,
    engine: BrowserEngine | None = None,
    headless: bool = False,
    viewport: dict[str, int] | None = None,
) -> Any:
    """Launch a Playwright persistent context using the preferred engine."""
    resolved = engine or preferred_engine()
    _ensure_playwright_browser_installed(resolved)
    user_data_dir = str(profile_dir(resolved))
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)

    launch_kwargs: dict[str, Any] = dict(
        user_data_dir=user_data_dir,
        headless=headless,
        viewport=viewport or {"width": 1280, "height": 800},
    )

    if resolved == "chromium":
        chrome_path = find_system_chrome()
        launch_kwargs.update(
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-default-apps",
                "--disable-popup-blocking",
                "--disable-sync",
                "--disable-translate",
            ],
            ignore_default_args=["--enable-automation"],
        )
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path
            logger.info("Using system Chrome: %s", chrome_path)
        browser_type = playwright.chromium
    else:
        browser_type = playwright.webkit
        logger.info("Using Playwright WebKit (Safari engine) — no Chrome required")

    return browser_type.launch_persistent_context(**launch_kwargs)


def _ensure_playwright_browser_installed(engine: BrowserEngine) -> None:
    """Best-effort auto-install for missing Playwright browser binaries."""
    install_target = "webkit" if engine == "webkit" else "chromium"
    if platform.system() != "Darwin" or install_target != "webkit":
        return
    if install_target in _checked_browser_installs:
        return
    try:
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", install_target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.warning("Playwright %s install check failed: %s", install_target, e)
    finally:
        _checked_browser_installs.add(install_target)


def read_platform_sessions(
    engine: BrowserEngine | None = None,
    *,
    open_context: Any | None = None,
) -> dict[str, bool]:
    """Return linkedin/indeed session flags from cookies."""
    result = {"linkedin": False, "indeed": False}
    indeed_cookies = frozenset({"INDEED_CSRF_TOKEN", "indeed_rcc"})

    cookies: list[dict[str, Any]]
    if open_context is not None:
        try:
            cookies = open_context.cookies()
        except Exception as e:
            logger.debug("Could not read cookies from open context: %s", e)
            return result
    else:
        cookies = _read_cookies_headless(engine)

    for cookie in cookies:
        name = cookie.get("name", "")
        domain = cookie.get("domain", "")
        if name == "li_at" and "linkedin" in domain:
            result["linkedin"] = True
        if name in indeed_cookies and "indeed" in domain:
            result["indeed"] = True
    return result


def _read_cookies_headless(engine: BrowserEngine | None = None) -> list[dict[str, Any]]:
    """Briefly open a headless profile to read persisted cookies."""
    resolved = engine or preferred_engine()
    root = profile_dir(resolved)
    if not root.exists():
        return []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    try:
        with sync_playwright() as playwright:
            context = launch_persistent_context(
                playwright,
                engine=resolved,
                headless=True,
            )
            cookies = context.cookies()
            context.close()
            return cookies
    except Exception as e:
        logger.debug("Headless cookie read failed: %s", e)
        return []
