"""Browser manager — persistent Playwright context for bot automation.

Implements: FR-043 (browser session management).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.browser_engine import launch_persistent_context, preferred_engine, profile_dir

if TYPE_CHECKING:
    from config.settings import AppConfig

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages a Playwright persistent browser context.

    Preserves login sessions between bot runs by using a persistent
    user data directory under ``~/.autoapply/``.
    """

    def __init__(self, config: "AppConfig") -> None:
        self.headless = config.bot.apply_mode != "watch"
        self.engine = preferred_engine()
        self.profile_dir = profile_dir(self.engine)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self._playwright: Any = None
        self._context: Any = None
        self._page: Any = None

    def get_page(self):
        """Get or create a Playwright Page in a persistent context.

        Returns:
            A Playwright Page instance.

        Raises:
            RuntimeError: If Playwright or the browser engine is not installed.
        """
        if self._page and not self._page.is_closed():
            return self._page

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is required but not installed. "
                "Run: pip install playwright && python -m playwright install chromium"
            )

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        try:
            self._context = launch_persistent_context(
                self._playwright,
                engine=self.engine,
                headless=self.headless,
            )
        except Exception as e:
            error_msg = str(e)
            if "executable doesn't exist" in error_msg.lower():
                install_cmd = (
                    "python -m playwright install webkit"
                    if self.engine == "webkit"
                    else "python -m playwright install chromium"
                )
                raise RuntimeError(
                    f"Playwright {self.engine} not installed. Run: {install_cmd}"
                )
            raise

        self._page = self._context.new_page()
        logger.info(
            "Browser started (engine=%s, headless=%s, profile=%s)",
            self.engine, self.headless, self.profile_dir,
        )
        return self._page

    def close(self) -> None:
        """Close the browser context and cleanup Playwright."""
        if self._context:
            try:
                self._context.close()
            except Exception as e:
                logger.debug("Failed to close browser context: %s", e)
            self._context = None
            self._page = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.debug("Failed to stop Playwright: %s", e)
            self._playwright = None

        logger.info("Browser closed")
