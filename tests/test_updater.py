"""Tests for in-app update helpers."""

from __future__ import annotations

import zipfile
from unittest.mock import patch

import pytest

from app import create_app
from core import updater
from core.version_info import get_app_version, is_newer_version, normalize_tag, parse_version


@pytest.fixture()
def client(tmp_path):
    with patch("config.settings.get_data_dir", return_value=tmp_path):
        flask_app, _ = create_app()
        flask_app.config["TESTING"] = True
        with flask_app.test_client() as c:
            yield c


class TestVersionInfo:
    def test_parse_version(self):
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("v2.0.0") == (2, 0, 0)

    def test_is_newer_version(self):
        assert is_newer_version("1.1.0", "1.0.0")
        assert not is_newer_version("1.0.0", "1.0.0")
        assert not is_newer_version("1.0.0", "2.0.0")

    def test_normalize_tag(self):
        assert normalize_tag("v1.0.1") == "1.0.1"

    def test_get_app_version_reads_pyproject(self):
        get_app_version.cache_clear()
        assert get_app_version() == "1.0.5"


class TestUpdater:
    def setup_method(self):
        updater._set_state(status="idle", progress=0, error="", ready=False)

    def test_pick_release_asset_prefers_platform(self):
        assets = [
            {"name": "JobApplyAssistant-1.0.0-linux-x64.zip", "size": 1},
            {"name": "JobApplyAssistant-1.0.0-win-x64.zip", "size": 2},
        ]
        with patch.object(updater, "get_platform_asset_suffix", return_value="win-x64"):
            picked = updater._pick_release_asset(assets)
        assert picked["name"].endswith("win-x64.zip")

    def test_check_for_updates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(updater, "get_app_version", lambda: "1.0.0")
        release = {
            "tag_name": "v1.1.0",
            "body": "Bug fixes",
            "assets": [
                {
                    "name": "JobApplyAssistant-1.1.0-win-x64.zip",
                    "size": 100,
                    "browser_download_url": "https://example.com/app.zip",
                }
            ],
        }
        with patch.object(updater, "_fetch_latest_release", return_value=release):
            with patch.object(updater, "get_platform_asset_suffix", return_value="win-x64"):
                result = updater.check_for_updates()
        assert result["update_available"] is True
        assert result["latest_version"] == "1.1.0"
        assert "Bug fixes" in result["release_notes"]

    def test_pick_release_asset_prefers_mac_arm64(self):
        assets = [
            {"name": "JobApplyAssistant-1.0.0-mac-x64.zip", "size": 1},
            {"name": "JobApplyAssistant-1.0.0-mac-arm64.zip", "size": 2},
        ]
        with patch.object(updater, "get_platform_asset_suffix", return_value="mac-arm64"):
            picked = updater._pick_release_asset(assets)
        assert picked["name"].endswith("mac-arm64.zip")

    def test_find_package_root(self, tmp_path):
        root = tmp_path / "JobApplyAssistant"
        root.mkdir()
        (root / updater.EXE_NAME).write_text("exe", encoding="utf-8")
        assert updater._find_package_root(tmp_path) == root

    def test_find_mac_app_bundle_root(self, tmp_path):
        app = tmp_path / "JobApplyAssistant.app" / "Contents" / "MacOS"
        app.mkdir(parents=True)
        (app / "JobApplyAssistant").write_text("bin", encoding="utf-8")
        assert updater._find_package_root(tmp_path).name == "JobApplyAssistant.app"

    def test_extract_and_find(self, tmp_path, monkeypatch):
        zip_path = tmp_path / "app.zip"
        pkg = tmp_path / "pkg" / "JobApplyAssistant"
        pkg.mkdir(parents=True)
        (pkg / updater.EXE_NAME).write_text("exe", encoding="utf-8")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(pkg / updater.EXE_NAME, f"JobApplyAssistant/{updater.EXE_NAME}")

        out = tmp_path / "out"
        updater._extract_zip(zip_path, out)
        found = updater._find_package_root(out)
        assert (found / updater.EXE_NAME).is_file()

    def test_updates_info_route(self, client):
        res = client.get("/api/updates/info")
        assert res.status_code == 200
        data = res.get_json()
        assert "current_version" in data
        assert "can_install" in data

    def test_updates_check_route(self, client, monkeypatch):
        monkeypatch.setattr(
            "routes.updates.check_for_updates",
            lambda: {
                "current_version": "1.0.0",
                "latest_version": "1.0.0",
                "update_available": False,
                "release_notes": "",
                "download_size": 0,
                "ready": False,
                "can_install": False,
            },
        )
        res = client.post("/api/updates/check")
        assert res.status_code == 200
        assert res.get_json()["update_available"] is False
