"""Import profile data from LinkedIn (browser scrape or data export ZIP)."""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from pathlib import Path
from typing import Any

from core.browser_profile import (
    cdp_reachable,
    ensure_profile_available_for_playwright,
    get_cdp_port,
    profile_dir,
)

logger = logging.getLogger(__name__)


def parse_linkedin_export_zip(zip_path: Path) -> str:
    """Build plain-text profile context from a LinkedIn 'Get a copy of your data' ZIP."""
    parts: list[str] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = {n.lower(): n for n in zf.namelist()}

        profile_name = _find_zip_member(names, ("profile.csv",))
        if profile_name:
            parts.append("=== LinkedIn Profile ===")
            parts.append(_csv_to_text(zf.read(profile_name)))

        for label, candidates in (
            ("Positions", ("positions.csv", "position.csv")),
            ("Education", ("education.csv",)),
            ("Skills", ("skills.csv",)),
            ("Certifications", ("certifications.csv",)),
            ("Languages", ("languages.csv",)),
            ("Projects", ("projects.csv",)),
        ):
            member = _find_zip_member(names, candidates)
            if member:
                parts.append(f"=== {label} ===")
                parts.append(_csv_to_text(zf.read(member)))

    result = "\n\n".join(p for p in parts if p.strip())
    if not result.strip():
        raise ValueError(
            "No recognizable LinkedIn export files found in ZIP. "
            "Export your data from LinkedIn Settings → Get a copy of your data."
        )
    return result


def _find_zip_member(names: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in names:
            return names[candidate]
        for key, original in names.items():
            if key.endswith("/" + candidate) or key.endswith("\\" + candidate):
                return original
    return None


def _csv_to_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    rows: list[str] = []
    for row in reader:
        values = [str(v).strip() for v in row.values() if v and str(v).strip()]
        if values:
            rows.append(" | ".join(values))
    return "\n".join(rows)


def scrape_linkedin_profile(profile_path: Path | None = None) -> dict[str, Any]:
    """Scrape the logged-in user's LinkedIn profile using Playwright.

    Reuses the open Platform Login Chrome via CDP when available instead of
    launching a second browser on the same profile (which Chrome blocks).

    Returns:
        Dict with profile_url and raw_text for LLM extraction.

    Raises:
        RuntimeError: If not logged in or scraping fails.
    """
    import time

    root = profile_path or profile_dir()
    root.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright is required for LinkedIn import. "
            "Run: pip install playwright && python -m playwright install chromium"
        ) from e

    sections: list[str] = []
    profile_url = ""

    with sync_playwright() as playwright:
        cdp_port = get_cdp_port(root)
        use_cdp = bool(cdp_port and cdp_reachable(cdp_port))
        own_context = False
        created_page = False
        browser = None
        context = None
        page = None

        try:
            if use_cdp:
                browser = playwright.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{cdp_port}",
                )
                context = browser.contexts[0] if browser.contexts else None
                if context is None:
                    raise RuntimeError(
                        "Could not attach to the login browser. "
                        "Close Chrome and click Open LinkedIn Login again."
                    )
                page = context.new_page()
                created_page = True
            else:
                ensure_profile_available_for_playwright(root)
                chrome_path = _find_system_chrome()
                launch_kwargs: dict[str, Any] = dict(
                    user_data_dir=str(root),
                    headless=True,
                    viewport={"width": 1280, "height": 900},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--remote-debugging-port=0",
                    ],
                    ignore_default_args=["--enable-automation"],
                )
                if chrome_path:
                    launch_kwargs["executable_path"] = chrome_path
                context = playwright.chromium.launch_persistent_context(**launch_kwargs)
                own_context = True
                page = context.new_page()
                created_page = True

            page.goto(
                "https://www.linkedin.com/in/me/",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            time.sleep(2)

            if "login" in page.url or "authwall" in page.url:
                raise RuntimeError(
                    "Not logged in to LinkedIn. Use Settings → Platform Login to sign in first."
                )

            profile_url = page.url.split("?")[0]

            _expand_sections(page)
            time.sleep(1)

            main_text = _extract_main_text(page)
            if main_text:
                sections.append(main_text)

            headline = _safe_inner_text(page, "div.text-body-medium, .pv-text-details__left-panel")
            if headline:
                sections.insert(0, f"Headline/About area:\n{headline}")

        finally:
            if page and created_page and not page.is_closed():
                try:
                    page.close()
                except Exception as e:
                    logger.debug("Could not close scrape tab: %s", e)
            if own_context and context is not None:
                try:
                    context.close()
                except Exception as e:
                    logger.debug("Could not close Playwright context: %s", e)

    raw_text = "\n\n".join(s for s in sections if s.strip())
    if len(raw_text.strip()) < 40:
        raise RuntimeError(
            "Could not read enough data from LinkedIn. "
            "Try importing a LinkedIn data export ZIP instead."
        )

    return {"profile_url": profile_url, "raw_text": raw_text}


def _expand_sections(page) -> None:
    """Click 'Show all' links to reveal more profile content."""
    selectors = [
        "a[id*='navigation-index-Show-all-experiences']",
        "button:has-text('Show all experiences')",
        "a:has-text('Show all experiences')",
        "a:has-text('Show all skills')",
        "button:has-text('Show all skills')",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                page.wait_for_timeout(800)
        except Exception as e:
            logger.debug("Could not expand LinkedIn section %s: %s", sel, e)


def _extract_main_text(page) -> str:
    selectors = [
        "main",
        "section.artdeco-card",
        "#profile-content",
        ".scaffold-layout__main",
    ]
    chunks: list[str] = []
    for sel in selectors:
        try:
            elements = page.query_selector_all(sel)
            for el in elements[:6]:
                text = (el.inner_text() or "").strip()
                if len(text) > 80:
                    chunks.append(text)
        except Exception as e:
            logger.debug("LinkedIn selector failed %s: %s", sel, e)
    seen: set[str] = set()
    unique: list[str] = []
    for chunk in chunks:
        key = chunk[:200]
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    return "\n\n".join(unique[:4])


def _safe_inner_text(page, selector: str) -> str:
    try:
        el = page.query_selector(selector)
        return (el.inner_text() or "").strip() if el else ""
    except Exception:
        return ""


def _find_system_chrome() -> str | None:
    import os
    import platform

    candidates: list[str] = []
    if platform.system() == "Windows":
        for base in [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.path.expandvars(r"%LOCALAPPDATA%"),
        ]:
            candidates.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    elif platform.system() == "Darwin":
        candidates.append("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    else:
        candidates.extend(["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"])

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None
