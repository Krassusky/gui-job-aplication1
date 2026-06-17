"""Platform detection helpers for packaging and updates."""

from __future__ import annotations

import platform
import sys

APP_NAME = "JobApplyAssistant"


def get_app_binary_name() -> str:
    """Return the packaged executable filename for the current OS."""
    if sys.platform == "win32":
        return f"{APP_NAME}.exe"
    return APP_NAME


def get_platform_asset_suffix() -> str:
    """Return the GitHub release asset suffix for the current machine."""
    if sys.platform == "win32":
        return "win-x64"
    if sys.platform == "darwin":
        machine = platform.machine().lower()
        if machine in {"arm64", "aarch64"}:
            return "mac-arm64"
        return "mac-x64"
    return "linux-x64"


def get_mac_app_bundle_name() -> str:
    return f"{APP_NAME}.app"
