# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AutoApply desktop application.

Implements: FR-096 (TASK-031).

Build:
    pyinstaller autoapply.spec

Output:
    dist/AutoApply/  (one-dir mode for faster startup)
"""

import os
import re
import sys
from pathlib import Path

block_cipher = None
_project_root = Path(SPECPATH)
_pyproject = (_project_root / "pyproject.toml").read_text(encoding="utf-8")
_app_version = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', _pyproject, re.MULTILINE)
APP_VERSION = _app_version.group(1) if _app_version else "0.0.0"
_icon_icns = _project_root / "static" / "icons" / "icon.icns"
_icon_ico = _project_root / "static" / "icons" / "icon.ico"

_datas = [
    (str(_project_root / "templates"), "templates"),
    (str(_project_root / "static"), "static"),
    (str(_project_root / "pyproject.toml"), "."),
    (str(_project_root / "LEIA-ME.txt"), "."),
    (str(_project_root / "LEIA-ME-MAC.txt"), "."),
]
_active_preset = _project_root / "presets" / ".active_preset"
if _active_preset.is_file():
    _preset_id = _active_preset.read_text(encoding="utf-8").strip()
    _preset_dir = _project_root / "presets" / _preset_id
    if _preset_dir.is_dir():
        _datas.append((str(_preset_dir), f"presets/{_preset_id}"))
        _datas.append((str(_active_preset), "presets"))

a = Analysis(
    [str(_project_root / "run.py")],
    pathex=[str(_project_root)],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        # Gevent + SocketIO
        "gevent",
        "gevent.monkey",
        "gevent._ssl3",
        "geventwebsocket",
        "engineio.async_drivers.gevent",
        # Flask + extensions
        "flask",
        "flask_socketio",
        # PyWebView
        "webview",
        "webview.platforms.winforms",
        "pythonnet",
        "clr_loader",
        "clr",
        # System tray
        "pystray",
        "PIL",
        # App modules
        "app",
        "app_state",
        "bot",
        "bot.bot",
        "bot.state",
        "bot.apply",
        "bot.apply.linkedin",
        "bot.search.linkedin",
        "config",
        "config.settings",
        "core",
        "core.shortcuts",
        "core.updater",
        "core.platform_info",
        "core.version_info",
        "core.career_workflow",
        "core.languages",
        "core.browser_profile",
        "core.linkedin_importer",
        "core.profile_extractor",
        "core.document_parser",
        "db",
        "db.database",
        "routes",
        "routes.shortcuts",
        "routes.updates",
        "routes.workflow",
        "shell",
        "shell.main",
        "shell.tray",
        "shell.single_instance",
        "shell.win_motw",
        "shell.mac_quarantine",
        "presets",
        "presets.bootstrap",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "test",
        "tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JobApplyAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed mode — no terminal
    disable_windowed_traceback=False,
    argv_emulation=True if sys.platform == "darwin" else False,
    target_arch=None,
    codesign_identity=os.environ.get("APPLE_SIGNING_IDENTITY") if sys.platform == "darwin" else None,
    entitlements_file=None,
    icon=str(_icon_ico) if sys.platform == "win32" and _icon_ico.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["Python.Runtime.dll"],
    name="JobApplyAssistant",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="JobApplyAssistant.app",
        icon=str(_icon_icns) if _icon_icns.is_file() else None,
        bundle_identifier="com.krassusky.jobapplyassistant",
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHighResolutionCapable": True,
        },
    )
