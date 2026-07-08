"""Shared helpers for the dedicated AutoApply browser profile."""

from __future__ import annotations

import logging
import platform
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from core.browser_engine import preferred_engine, profile_dir as engine_profile_dir

logger = logging.getLogger(__name__)


def profile_dir() -> Path:
    return engine_profile_dir(preferred_engine())


def get_cdp_port(profile: Path | None = None) -> int | None:
    """Return the Chrome DevTools port for the login profile, if available."""
    root = profile or profile_dir()
    port_file = root / "DevToolsActivePort"
    if not port_file.exists():
        return None
    try:
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0].strip())
        return port if port > 0 else None
    except (OSError, ValueError, IndexError):
        return None


def cdp_reachable(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version",
            timeout=2,
        ) as resp:
            return bool(resp.status == 200)
    except (OSError, urllib.error.URLError, ValueError):
        return False


def profile_chrome_running(profile: Path | None = None) -> bool:
    """Return True if any Chrome process is using the login profile directory."""
    marker = str(profile or profile_dir())
    system = platform.system()
    try:
        if system == "Windows":
            escaped = marker.replace("'", "''")
            ps_cmd = (
                "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
                f"Where-Object {{ $_.CommandLine -like '*{escaped}*' }} | "
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


def kill_profile_chrome(profile: Path | None = None) -> None:
    """Force-close Chrome processes bound to the login profile directory."""
    marker = str(profile or profile_dir()).replace("'", "''")
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
                timeout=15,
            )
        else:
            subprocess.run(
                ["pkill", "-f", str(profile or profile_dir())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
    except Exception as e:
        logger.debug("Failed to kill profile Chrome processes: %s", e)


def ensure_profile_available_for_playwright(profile: Path | None = None) -> None:
    """Close a stale Chrome session so Playwright can use the profile."""
    root = profile or profile_dir()
    port = get_cdp_port(root)
    if port and cdp_reachable(port):
        return
    if profile_chrome_running(root):
        logger.info("Closing stale Chrome on profile before Playwright launch")
        kill_profile_chrome(root)
        time.sleep(0.75)
