"""Tests for desktop shortcut installation (packaged builds)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.shortcuts import (
    ShortcutError,
    create_desktop_shortcut,
    get_app_launch_target,
    get_install_dir,
    install_shortcuts,
    is_shortcuts_available,
    mark_shortcuts_declined,
    mark_shortcuts_installed,
    needs_shortcuts_prompt,
)


@pytest.fixture
def frozen_win_exe(tmp_path, monkeypatch):
    install_dir = tmp_path / "JobApplyAssistant"
    install_dir.mkdir()
    exe = install_dir / "JobApplyAssistant.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "win32")
    return exe


@pytest.fixture
def frozen_mac_app(tmp_path, monkeypatch):
    app = tmp_path / "JobApplyAssistant.app"
    macos_dir = app / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True)
    binary = macos_dir / "JobApplyAssistant"
    binary.write_bytes(b"\x00")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(binary))
    monkeypatch.setattr(sys, "platform", "darwin")
    return app


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("core.shortcuts.get_data_dir", lambda: tmp_path)
    return tmp_path


class TestPathResolution:
    def test_windows_launch_target(self, frozen_win_exe):
        assert get_app_launch_target() == frozen_win_exe
        assert get_install_dir() == frozen_win_exe.parent

    def test_mac_launch_target(self, frozen_mac_app):
        assert get_app_launch_target() == frozen_mac_app
        assert get_install_dir() == frozen_mac_app.parent

    def test_not_frozen_returns_none(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        assert get_app_launch_target() is None


class TestAvailability:
    def test_unavailable_in_dev_mode(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        assert is_shortcuts_available() is False

    def test_available_when_frozen_windows(self, frozen_win_exe):
        assert is_shortcuts_available() is True

    def test_needs_prompt_when_fresh(self, frozen_win_exe, data_dir):
        assert needs_shortcuts_prompt() is True

    def test_no_prompt_after_install(self, frozen_win_exe, data_dir):
        mark_shortcuts_installed(["desktop"])
        assert needs_shortcuts_prompt() is False

    def test_no_prompt_after_decline(self, frozen_win_exe, data_dir):
        mark_shortcuts_declined()
        assert needs_shortcuts_prompt() is False


class TestWindowsShortcuts:
    def test_create_desktop_shortcut(self, frozen_win_exe, data_dir, monkeypatch):
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return MagicMock(returncode=0, stderr="")

        monkeypatch.setattr("core.shortcuts.subprocess.run", fake_run)
        monkeypatch.setattr(
            "core.shortcuts._desktop_dir",
            lambda: frozen_win_exe.parent / "Desktop",
        )

        path = create_desktop_shortcut()
        assert path.name == "Job Apply Assistant.lnk"
        assert calls
        assert calls[0][0] == "powershell"

    def test_create_start_menu_shortcut(self, frozen_win_exe, data_dir, monkeypatch):
        from core.shortcuts import create_start_menu_shortcut

        monkeypatch.setattr(
            "core.shortcuts.subprocess.run",
            lambda *a, **k: MagicMock(returncode=0, stderr=""),
        )
        path = create_start_menu_shortcut()
        assert path is not None
        assert path.name == "Job Apply Assistant.lnk"

    def test_install_shortcuts_windows(self, frozen_win_exe, data_dir, monkeypatch):
        monkeypatch.setattr(
            "core.shortcuts.subprocess.run",
            lambda *a, **k: MagicMock(returncode=0, stderr=""),
        )
        monkeypatch.setattr(
            "core.shortcuts._desktop_dir",
            lambda: frozen_win_exe.parent / "Desktop",
        )
        monkeypatch.setattr("core.shortcuts.desktop_shortcut_exists", lambda: True)
        monkeypatch.setattr("core.shortcuts.start_menu_shortcut_exists", lambda: True)

        result = install_shortcuts()
        assert result["success"] is True
        state = json.loads((data_dir / "shortcuts.json").read_text(encoding="utf-8"))
        assert state["installed"] is True


class TestMacShortcuts:
    def test_install_to_applications(self, frozen_mac_app, data_dir, monkeypatch, tmp_path):
        from core.shortcuts import install_to_applications

        apps = tmp_path / "Applications"
        apps.mkdir()
        monkeypatch.setattr("core.shortcuts._applications_path", lambda: apps / "JobApplyAssistant.app")

        dest = install_to_applications()
        assert dest is not None
        assert dest.is_dir()

    def test_install_shortcuts_mac(self, frozen_mac_app, data_dir, monkeypatch, tmp_path):
        apps = tmp_path / "Applications"
        apps.mkdir()
        monkeypatch.setattr("core.shortcuts._applications_path", lambda: apps / "JobApplyAssistant.app")
        monkeypatch.setattr(
            "core.shortcuts.subprocess.run",
            lambda *a, **k: MagicMock(returncode=0, stderr=""),
        )
        monkeypatch.setattr("core.shortcuts.desktop_shortcut_exists", lambda: True)
        monkeypatch.setattr("core.shortcuts.applications_installed", lambda: True)

        result = install_shortcuts()
        assert result["success"] is True


class TestShortcutsAPI:
    @pytest.fixture
    def app_client(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("app.get_data_dir", lambda: tmp_path)
        monkeypatch.setenv("AUTOAPPLY_DEV", "1")
        from app import create_app

        flask_app, _ = create_app()
        flask_app.config["TESTING"] = True
        with flask_app.test_client() as client:
            yield client

    def test_status_unavailable_in_dev(self, app_client):
        res = app_client.get("/api/shortcuts/status")
        assert res.status_code == 200
        data = res.get_json()
        assert data["available"] is False

    def test_install_rejected_in_dev(self, app_client):
        res = app_client.post("/api/shortcuts/install")
        assert res.status_code == 400

    def test_install_when_frozen(self, app_client, frozen_win_exe, data_dir, monkeypatch):
        monkeypatch.setattr(
            "core.shortcuts.subprocess.run",
            lambda *a, **k: MagicMock(returncode=0, stderr=""),
        )
        monkeypatch.setattr(
            "core.shortcuts._desktop_dir",
            lambda: frozen_win_exe.parent / "Desktop",
        )
        monkeypatch.setattr("core.shortcuts.desktop_shortcut_exists", lambda: True)
        monkeypatch.setattr("core.shortcuts.start_menu_shortcut_exists", lambda: True)

        res = app_client.post("/api/shortcuts/install")
        assert res.status_code == 200
        assert res.get_json()["success"] is True

    def test_decline(self, app_client, frozen_win_exe, data_dir):
        res = app_client.post("/api/shortcuts/decline")
        assert res.status_code == 200
        assert res.get_json()["declined"] is True


class TestIdempotency:
    def test_second_install_succeeds(self, frozen_win_exe, data_dir, monkeypatch):
        monkeypatch.setattr(
            "core.shortcuts.subprocess.run",
            lambda *a, **k: MagicMock(returncode=0, stderr=""),
        )
        monkeypatch.setattr(
            "core.shortcuts._desktop_dir",
            lambda: frozen_win_exe.parent / "Desktop",
        )
        monkeypatch.setattr("core.shortcuts.desktop_shortcut_exists", lambda: False)
        monkeypatch.setattr("core.shortcuts.start_menu_shortcut_exists", lambda: False)

        install_shortcuts()
        monkeypatch.setattr("core.shortcuts.desktop_shortcut_exists", lambda: True)
        monkeypatch.setattr("core.shortcuts.start_menu_shortcut_exists", lambda: True)
        result = install_shortcuts()
        assert result["success"] is True


class TestShortcutError:
    def test_powershell_failure_raises(self, frozen_win_exe, data_dir, monkeypatch):
        monkeypatch.setattr(
            "core.shortcuts.subprocess.run",
            lambda *a, **k: MagicMock(returncode=1, stderr="boom"),
        )
        monkeypatch.setattr(
            "core.shortcuts._desktop_dir",
            lambda: frozen_win_exe.parent / "Desktop",
        )
        with pytest.raises(ShortcutError):
            create_desktop_shortcut()


class TestPackagingReferences:
    def test_ci_package_includes_install_scripts(self):
        content = Path("scripts/ci_package.sh").read_text(encoding="utf-8")
        assert "install_shortcuts_win.bat" in content
        assert "install_shortcuts_mac.command" in content

    def test_spec_includes_shortcuts_module(self):
        content = Path("autoapply.spec").read_text(encoding="utf-8")
        assert "core.shortcuts" in content
