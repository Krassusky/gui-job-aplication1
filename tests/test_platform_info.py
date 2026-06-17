"""Tests for platform detection helpers."""

from __future__ import annotations

from unittest.mock import patch

from core.platform_info import (
    APP_NAME,
    get_app_binary_name,
    get_mac_app_bundle_name,
    get_platform_asset_suffix,
)


class TestPlatformInfo:
    def test_app_binary_name_windows(self):
        with patch("core.platform_info.sys.platform", "win32"):
            assert get_app_binary_name() == f"{APP_NAME}.exe"

    def test_app_binary_name_mac(self):
        with patch("core.platform_info.sys.platform", "darwin"):
            assert get_app_binary_name() == APP_NAME

    def test_platform_suffix_mac_arm64(self):
        with patch("core.platform_info.sys.platform", "darwin"):
            with patch("core.platform_info.platform.machine", return_value="arm64"):
                assert get_platform_asset_suffix() == "mac-arm64"

    def test_platform_suffix_mac_intel(self):
        with patch("core.platform_info.sys.platform", "darwin"):
            with patch("core.platform_info.platform.machine", return_value="x86_64"):
                assert get_platform_asset_suffix() == "mac-x64"

    def test_mac_app_bundle_name(self):
        assert get_mac_app_bundle_name() == "JobApplyAssistant.app"
