"""Tests for Windows Mark-of-the-Web stripping."""

from __future__ import annotations

import sys
from unittest.mock import patch

from shell.win_motw import _should_unblock_dll, strip_download_zone_identifiers


class TestShouldUnblockDll:
    def test_python_runtime_dll(self):
        assert _should_unblock_dll("Python.Runtime.dll", r"C:\app\_internal\pythonnet\runtime")

    def test_ignores_unrelated_dll(self):
        assert not _should_unblock_dll("sqlite3.dll", r"C:\app\_internal")


class TestStripDownloadZoneIdentifiers:
    def test_noop_off_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        assert strip_download_zone_identifiers() == 0

    def test_noop_when_not_frozen(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        assert strip_download_zone_identifiers() == 0

    def test_removes_zone_identifier_ads(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

        runtime_dir = tmp_path / "pythonnet" / "runtime"
        runtime_dir.mkdir(parents=True)
        dll = runtime_dir / "Python.Runtime.dll"
        dll.write_bytes(b"MZ")

        removed_paths: list[str] = []

        def fake_remove(path: str) -> None:
            removed_paths.append(path)

        walk_data = [(str(runtime_dir), [], ["Python.Runtime.dll"])]

        with patch("shell.win_motw.os.walk", return_value=walk_data), patch(
            "shell.win_motw.os.remove", side_effect=fake_remove
        ):
            count = strip_download_zone_identifiers()

        assert count == 1
        assert removed_paths == [str(dll) + ":Zone.Identifier"]
