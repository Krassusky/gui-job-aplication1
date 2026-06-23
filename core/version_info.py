"""Application version helpers."""

from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

_VERSION_RE = re.compile(r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)")


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a semver string into (major, minor, patch). Unknown parts become 0."""
    if not version:
        return (0, 0, 0)
    match = _VERSION_RE.match(version.strip())
    if not match:
        return (0, 0, 0)
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def is_newer_version(latest: str, current: str) -> bool:
    """Return True if *latest* is strictly newer than *current*."""
    return parse_version(latest) > parse_version(current)


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Return the installed application version."""
    repo_root = Path(__file__).resolve().parent.parent
    repo_version = _read_pyproject_version(repo_root / "pyproject.toml")

    # Source/dev runs: repo pyproject.toml is authoritative (avoids stale pip metadata).
    if not getattr(sys, "frozen", False) and repo_version:
        return repo_version

    try:
        from importlib.metadata import version

        return version("jobapply-assistant")
    except Exception:
        pass

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            ver = _read_pyproject_version(Path(meipass) / "pyproject.toml")
            if ver:
                return ver

    return repo_version or "0.0.0"


def normalize_tag(tag: str) -> str:
    """Strip leading ``v`` from a git tag."""
    return tag.lstrip("v").strip()


def _read_pyproject_version(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return match.group(1) if match else None
