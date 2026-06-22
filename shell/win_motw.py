"""Windows Mark-of-the-Web helpers for frozen pywebview/pythonnet builds."""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)


def _bundle_root() -> str | None:
    """Return the PyInstaller bundle directory when running frozen."""
    if not getattr(sys, "frozen", False):
        return None
    return getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(sys.executable))


def _should_unblock_dll(filename: str, directory: str) -> bool:
    low_name = filename.lower()
    low_dir = directory.lower()
    if not low_name.endswith(".dll"):
        return False
    return (
        low_name.startswith("python.runtime")
        or "pythonnet" in low_dir
        or "clr_loader" in low_dir
    )


def strip_download_zone_identifiers() -> int:
    """Remove Zone.Identifier ADS from bundled .NET assemblies.

    Files extracted from a downloaded ZIP inherit Mark-of-the-Web, which
    prevents pythonnet from loading ``Python.Runtime.dll`` on first launch.
    """
    if sys.platform != "win32":
        return 0

    base = _bundle_root()
    if not base:
        return 0

    removed = 0
    try:
        for root, _dirs, files in os.walk(base):
            for filename in files:
                if not _should_unblock_dll(filename, root):
                    continue
                ads_path = os.path.join(root, filename) + ":Zone.Identifier"
                try:
                    os.remove(ads_path)
                    removed += 1
                except OSError:
                    pass
    except OSError as exc:
        logger.debug("Could not walk bundle for MOTW strip: %s", exc)

    if removed:
        logger.info("Stripped Mark-of-the-Web from %d bundled assemblies", removed)
    return removed
