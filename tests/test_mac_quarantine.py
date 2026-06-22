"""Tests for macOS quarantine stripping."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

from shell.mac_quarantine import _app_bundle_path, strip_download_quarantine


class TestAppBundlePath:
    def test_resolves_app_bundle(self, tmp_path, monkeypatch):
        app = tmp_path / "JobApplyAssistant.app"
        macos = app / "Contents" / "MacOS"
        macos.mkdir(parents=True)
        binary = macos / "JobApplyAssistant"
        binary.write_bytes(b"\x00")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(binary))
        monkeypatch.setattr(sys, "platform", "darwin")
        assert _app_bundle_path() == app

    def test_returns_none_off_mac(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        assert _app_bundle_path() is None


class TestStripDownloadQuarantine:
    def test_noop_off_mac(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        assert strip_download_quarantine() is False

    def test_runs_xattr_on_mac(self, tmp_path, monkeypatch):
        app = tmp_path / "JobApplyAssistant.app"
        app.mkdir()
        monkeypatch.setattr(sys, "platform", "darwin")

        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return MagicMock(returncode=0, stderr="")

        monkeypatch.setattr("shell.mac_quarantine.subprocess.run", fake_run)
        assert strip_download_quarantine(app) is True
        assert calls[0][:3] == ["xattr", "-dr", "com.apple.quarantine"]
