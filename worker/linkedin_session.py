"""LinkedIn session helpers for the headless Job Hunter."""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)


def linkedin_credentials_from_env() -> tuple[str, str] | None:
    email = os.environ.get("LINKEDIN_EMAIL", "").strip()
    password = os.environ.get("LINKEDIN_PASSWORD", "").strip()
    if email and password:
        return email, password
    return None


def ensure_linkedin_session(page) -> bool:
    """If LinkedIn shows a login wall, try email/password from env.

    Returns True if the page looks usable for search (logged in or no wall).
    """
    try:
        page.goto(
            "https://www.linkedin.com/jobs/search/",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        time.sleep(2)
    except Exception as e:
        logger.warning("Could not open LinkedIn jobs page: %s", e)
        return False

    url = (page.url or "").lower()
    if "login" not in url and "authwall" not in url and "checkpoint" not in url:
        return True

    creds = linkedin_credentials_from_env()
    if not creds:
        logger.error(
            "LinkedIn login required but LINKEDIN_EMAIL/PASSWORD are not set in .env"
        )
        return False

    email, password = creds
    logger.info("Attempting LinkedIn auto-login for %s", email)
    try:
        # Prefer the standard login form if present; otherwise go to login URL.
        if "login" not in url:
            page.goto(
                "https://www.linkedin.com/login",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(1)

        email_sel = 'input#username, input[name="session_key"]'
        pass_sel = 'input#password, input[name="session_password"]'
        page.wait_for_selector(email_sel, timeout=15000)
        page.fill(email_sel, email)
        page.fill(pass_sel, password)
        page.click('button[type="submit"]')
        time.sleep(4)

        # Challenge / CAPTCHA / 2FA — cannot complete headless.
        cur = (page.url or "").lower()
        if any(x in cur for x in ("checkpoint", "challenge", "captcha", "login")):
            logger.error(
                "LinkedIn login needs manual verification (2FA/captcha). "
                "Log in once on this machine, then restart the hunter."
            )
            return False
        logger.info("LinkedIn auto-login succeeded")
        return True
    except Exception as e:
        logger.exception("LinkedIn auto-login failed: %s", e)
        return False
