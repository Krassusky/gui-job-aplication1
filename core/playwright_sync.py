"""Run Playwright Sync API off the Flask/gevent request thread.

Playwright's sync API refuses to start when ``asyncio.get_running_loop()``
succeeds in the current thread (common under Flask-SocketIO + gevent).
All sync Playwright work must run on a plain OS thread with no running
asyncio loop. Long-lived login browsers stay on one dedicated worker so
Playwright greenlets are never resumed from another thread.
"""

from __future__ import annotations

import concurrent.futures
import logging
import queue
import threading
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def run_in_playwright_thread(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Execute ``fn`` on a fresh OS thread and return its result."""
    box: dict[str, Any] = {}

    def _target() -> None:
        try:
            box["result"] = fn(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 — re-raised for caller
            box["error"] = exc

    thread = threading.Thread(
        target=_target,
        name="playwright-sync",
        daemon=True,
    )
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box["result"]


class LoginPlaywrightWorker:
    """Owns the platform-login Playwright browser on a single OS thread."""

    def __init__(self) -> None:
        self._cmds: queue.Queue[
            tuple[str, tuple[Any, ...], dict[str, Any], concurrent.futures.Future[Any]]
            | None
        ] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        self._playwright: Any = None
        self._context: Any = None
        self._engine: str | None = None

    def _ensure_thread(self) -> None:
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._loop,
                name="login-playwright",
                daemon=True,
            )
            self._thread.start()

    def _loop(self) -> None:
        while True:
            item = self._cmds.get()
            if item is None:
                self._shutdown_browser()
                break
            op, args, kwargs, fut = item
            try:
                handler = getattr(self, f"_op_{op}")
                fut.set_result(handler(*args, **kwargs))
            except BaseException as exc:  # noqa: BLE001 — forwarded via Future
                fut.set_exception(exc)

    def _submit(self, op: str, *args: Any, timeout: float = 120, **kwargs: Any) -> Any:
        self._ensure_thread()
        fut: concurrent.futures.Future[Any] = concurrent.futures.Future()
        self._cmds.put((op, args, kwargs, fut))
        return fut.result(timeout=timeout)

    def open(self, url: str, engine: str) -> str:
        """Open or navigate the login browser. Returns status string."""
        return self._submit("open", url, engine)

    def alive(self) -> bool:
        """Return True if the Playwright login browser still has pages."""
        if self._thread is None or not self._thread.is_alive():
            return False
        try:
            return bool(self._submit("alive", timeout=10))
        except Exception as e:
            logger.debug("Login Playwright alive check failed: %s", e)
            return False

    def close(self) -> None:
        """Close the login browser (keeps the worker thread for reuse)."""
        if self._thread is None or not self._thread.is_alive():
            return
        try:
            self._submit("close", timeout=30)
        except Exception as e:
            logger.debug("Login Playwright close failed: %s", e)

    def sessions(self) -> dict[str, bool]:
        """Read LinkedIn/Indeed session cookies from the open context."""
        return self._submit("sessions", timeout=30)

    def has_context(self) -> bool:
        """Return True if this worker currently owns an open context."""
        if self._thread is None or not self._thread.is_alive():
            return False
        try:
            return bool(self._submit("has_context", timeout=10))
        except Exception:
            return False

    def _op_open(self, url: str, engine: str) -> str:
        from playwright.sync_api import sync_playwright

        from core.browser_engine import engine_display_name, launch_persistent_context

        if self._context is not None:
            try:
                pages = self._context.pages
                page = pages[0] if pages else self._context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                logger.info("Login browser navigated in existing session: %s", url)
                return "navigated"
            except Exception as e:
                logger.debug("Existing login context unusable, relaunching: %s", e)
                self._shutdown_browser()

        self._playwright = sync_playwright().start()
        self._context = launch_persistent_context(
            self._playwright,
            engine=engine,
            headless=False,
        )
        page = self._context.pages[0] if self._context.pages else self._context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        self._engine = engine
        logger.info(
            "Login browser opened (%s): %s",
            engine_display_name(engine),
            url,
        )
        return "opening"

    def _op_alive(self) -> bool:
        if self._context is None:
            return False
        try:
            return bool(self._context.pages)
        except Exception:
            self._shutdown_browser()
            return False

    def _op_has_context(self) -> bool:
        return self._context is not None

    def _op_close(self) -> None:
        self._shutdown_browser()

    def _op_sessions(self) -> dict[str, bool]:
        from core.browser_engine import read_platform_sessions

        if self._context is None:
            return {"linkedin": False, "indeed": False}
        return read_platform_sessions(self._engine, open_context=self._context)

    def _shutdown_browser(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception as e:
                logger.debug("Failed to close Playwright login context: %s", e)
            self._context = None

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.debug("Failed to stop Playwright login instance: %s", e)
            self._playwright = None

        self._engine = None


# Process-wide singleton used by login routes and graceful shutdown.
login_playwright_worker = LoginPlaywrightWorker()
