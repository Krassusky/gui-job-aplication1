"""Desktop and Start Menu shortcut helpers for packaged builds."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from config.settings import get_data_dir
from core.platform_info import get_mac_app_bundle_name

logger = logging.getLogger(__name__)

SHORTCUT_DISPLAY_NAME = "Job Apply Assistant"
_STATE_FILE = "shortcuts.json"


class ShortcutError(Exception):
    """Raised when shortcut installation fails."""


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_shortcuts_available() -> bool:
    """Shortcut installation is only supported in packaged builds."""
    return is_frozen_app() and sys.platform in ("win32", "darwin")


def _state_path() -> Path:
    return get_data_dir() / _STATE_FILE


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Could not read shortcuts state: %s", e)
        return {}


def _save_state(state: dict[str, Any]) -> None:
    path = _state_path()
    get_data_dir().mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def mark_shortcuts_declined() -> None:
    state = _load_state()
    state["declined"] = True
    _save_state(state)


def mark_shortcuts_installed(targets: list[str]) -> None:
    state = _load_state()
    state.update({
        "installed": True,
        "declined": False,
        "platform": sys.platform,
        "targets": targets,
    })
    _save_state(state)


def needs_shortcuts_prompt() -> bool:
    if not is_shortcuts_available():
        return False
    state = _load_state()
    return not state.get("installed") and not state.get("declined")


def get_app_launch_target() -> Path | None:
    """Return the executable (Windows) or .app bundle (macOS) path."""
    if not is_frozen_app():
        return None

    exe = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        # .../JobApplyAssistant.app/Contents/MacOS/JobApplyAssistant
        if exe.parent.name == "MacOS" and exe.parent.parent.name == "Contents":
            return exe.parent.parent.parent
        return None
    if sys.platform == "win32":
        return exe
    return None


def get_install_dir() -> Path | None:
    """Return the folder containing the packaged app."""
    target = get_app_launch_target()
    if target is None:
        return None
    if sys.platform == "darwin":
        return target.parent
    return target.parent


def _desktop_dir() -> Path:
    if sys.platform == "win32":
        user_profile = os.environ.get("USERPROFILE", str(Path.home()))
        return Path(user_profile) / "Desktop"
    return Path.home() / "Desktop"


def _desktop_shortcut_path() -> Path:
    if sys.platform == "win32":
        return _desktop_dir() / f"{SHORTCUT_DISPLAY_NAME}.lnk"
    return _desktop_dir() / SHORTCUT_DISPLAY_NAME


def _start_menu_shortcut_path() -> Path:
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{SHORTCUT_DISPLAY_NAME}.lnk"


def _applications_path() -> Path:
    return Path("/Applications") / get_mac_app_bundle_name()


def desktop_shortcut_exists() -> bool:
    path = _desktop_shortcut_path()
    if sys.platform == "win32":
        return path.is_file()
    if path.exists():
        return True
    # Finder aliases may use the .app display name
    alt = _desktop_dir() / get_mac_app_bundle_name()
    return alt.exists()


def start_menu_shortcut_exists() -> bool:
    if sys.platform != "win32":
        return False
    return _start_menu_shortcut_path().is_file()


def applications_installed() -> bool:
    if sys.platform != "darwin":
        return False
    target = get_app_launch_target()
    apps = _applications_path()
    if target is None:
        return apps.is_dir()
    try:
        return target.resolve() == apps.resolve()
    except OSError:
        return apps.is_dir()


def _ps_escape(value: str) -> str:
    return value.replace("'", "''")


def _create_windows_lnk(lnk_path: Path, target: Path, work_dir: Path) -> None:
    lnk = _ps_escape(str(lnk_path))
    tgt = _ps_escape(str(target))
    work = _ps_escape(str(work_dir))
    icon = _ps_escape(f"{target},0")
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
        f"$s.TargetPath = '{tgt}';"
        f"$s.WorkingDirectory = '{work}';"
        f"$s.IconLocation = '{icon}';"
        f"$s.Save()"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ShortcutError(result.stderr.strip() or "Failed to create Windows shortcut")


def create_desktop_shortcut() -> Path:
    target = get_app_launch_target()
    install_dir = get_install_dir()
    if target is None or install_dir is None:
        raise ShortcutError("Packaged app path not found")

    lnk_path = _desktop_shortcut_path()
    lnk_path.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        _create_windows_lnk(lnk_path, target, install_dir)
        return lnk_path

    if desktop_shortcut_exists():
        return _desktop_shortcut_path()

    app_target = target if target.suffix == ".app" or target.name.endswith(".app") else target
    if sys.platform == "darwin" and app_target.is_dir():
        launch_target = _applications_path() if applications_installed() else app_target
        script = (
            'tell application "Finder"\n'
            f'  make alias file at desktop to POSIX file "{launch_target}"\n'
            "end tell"
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ShortcutError(result.stderr.strip() or "Failed to create macOS desktop alias")
        return _desktop_shortcut_path()

    raise ShortcutError(f"Unsupported platform: {sys.platform}")


def create_start_menu_shortcut() -> Path | None:
    if sys.platform != "win32":
        return None

    target = get_app_launch_target()
    install_dir = get_install_dir()
    if target is None or install_dir is None:
        raise ShortcutError("Packaged app path not found")

    lnk_path = _start_menu_shortcut_path()
    lnk_path.parent.mkdir(parents=True, exist_ok=True)
    _create_windows_lnk(lnk_path, target, install_dir)
    return lnk_path


def install_to_applications() -> Path | None:
    if sys.platform != "darwin":
        return None

    source = get_app_launch_target()
    if source is None or not source.is_dir():
        raise ShortcutError("macOS app bundle not found")

    dest = _applications_path()
    if applications_installed():
        return dest

    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(source, dest, symlinks=True)
    return dest


def install_shortcuts() -> dict[str, Any]:
    """Create platform shortcuts and persist install state."""
    if not is_shortcuts_available():
        raise ShortcutError("Shortcuts are only available in packaged builds")

    created: list[str] = []

    if sys.platform == "win32":
        desktop = create_desktop_shortcut()
        created.append(str(desktop))
        start_menu = create_start_menu_shortcut()
        if start_menu:
            created.append(str(start_menu))
    elif sys.platform == "darwin":
        apps = install_to_applications()
        if apps:
            created.append(str(apps))
        desktop = create_desktop_shortcut()
        created.append(str(desktop))

    mark_shortcuts_installed(created)
    return {
        "success": True,
        "targets": created,
        "desktop_exists": desktop_shortcut_exists(),
        "start_menu_exists": start_menu_shortcut_exists(),
        "applications_installed": applications_installed(),
    }


def get_shortcuts_status() -> dict[str, Any]:
    return {
        "available": is_shortcuts_available(),
        "needs_prompt": needs_shortcuts_prompt(),
        "installed": bool(_load_state().get("installed")),
        "declined": bool(_load_state().get("declined")),
        "platform": sys.platform,
        "desktop_exists": desktop_shortcut_exists() if is_shortcuts_available() else False,
        "start_menu_exists": start_menu_shortcut_exists() if is_shortcuts_available() else False,
        "applications_installed": applications_installed() if is_shortcuts_available() else False,
        "app_target": str(get_app_launch_target() or ""),
        "install_dir": str(get_install_dir() or ""),
    }
