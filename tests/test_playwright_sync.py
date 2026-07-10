"""Tests for Playwright sync helpers (asyncio-loop isolation)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from core.playwright_sync import LoginPlaywrightWorker, run_in_playwright_thread


def test_run_in_playwright_thread_returns_value():
    assert run_in_playwright_thread(lambda: 42) == 42


def test_run_in_playwright_thread_propagates_errors():
    def _boom():
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        run_in_playwright_thread(_boom)


def test_run_in_playwright_thread_escapes_running_asyncio_loop():
    """Sync Playwright must not see the caller's asyncio loop."""

    def _probe() -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    async def _caller() -> bool:
        # Inside an asyncio loop here; the helper must run on a clean thread.
        return run_in_playwright_thread(_probe)

    assert asyncio.run(_caller()) is False


def test_login_worker_open_navigate_close():
    worker = LoginPlaywrightWorker()
    fake_page = MagicMock()
    fake_context = MagicMock()
    fake_context.pages = [fake_page]
    fake_pw = MagicMock()

    with (
        patch("playwright.sync_api.sync_playwright") as mock_sync,
        patch(
            "core.browser_engine.launch_persistent_context",
            return_value=fake_context,
        ),
        patch("core.browser_engine.engine_display_name", return_value="WebKit"),
    ):
        mock_sync.return_value.start.return_value = fake_pw

        status = worker.open("https://www.linkedin.com/login", "webkit")
        assert status == "opening"
        assert worker.alive() is True
        assert worker.has_context() is True

        status2 = worker.open("https://www.linkedin.com/feed/", "webkit")
        assert status2 == "navigated"
        fake_page.goto.assert_called()

        worker.close()
        assert worker.alive() is False
        fake_context.close.assert_called()
        fake_pw.stop.assert_called()
