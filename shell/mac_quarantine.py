"""macOS quarantine helpers for downloaded app bundles."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_QUARANTINE_ATTR = "com.apple.quarantine"


def _app_bundle_path() -> Path | None:
    if not getattr(sys, "frozen", False) or sys.platform != "darwin":
        return None
    exe = Path(sys.executable).resolve()
    if exe.parent.name == "MacOS" and exe.parent.parent.name == "Contents":
        return exe.parent.parent.parent
    return None


def strip_download_quarantine(target: Path | None = None) -> bool:
    """Remove Gatekeeper quarantine from the app bundle (best-effort).

    Downloaded ZIPs tag apps with ``com.apple.quarantine``, which blocks
    first launch until the user right-clicks → Open. Clearing it makes
    double-click work like a normal installed app.
    """
    if sys.platform != "darwin":
        return False

    path = target or _app_bundle_path()
    if path is None or not path.exists():
        return False

    try:
        result = subprocess.run(
            ["xattr", "-dr", _QUARANTINE_ATTR, str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        logger.debug("Could not run xattr: %s", exc)
        return False

    if result.returncode == 0:
        logger.info("Removed macOS quarantine from %s", path)
        return True

    if result.stderr:
        logger.debug("xattr stderr: %s", result.stderr.strip())
    return False
