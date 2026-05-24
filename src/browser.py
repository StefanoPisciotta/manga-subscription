from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import BrowserContext, Playwright, sync_playwright

try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None

from src.config import PROFILE_DIR

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1366, "height": 900}
LOCALE = "it-IT"
TIMEZONE = "Europe/Rome"


@contextmanager
def launch_context(headless: bool = True) -> Iterator[BrowserContext]:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = _new_context(pw, headless=headless)
        try:
            yield context
        finally:
            context.close()


def _new_context(pw: Playwright, headless: bool) -> BrowserContext:
    context = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        locale=LOCALE,
        timezone_id=TIMEZONE,
        viewport=VIEWPORT,
        user_agent=USER_AGENT,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    if stealth_sync is not None:
        for page in context.pages:
            stealth_sync(page)
        context.on("page", lambda p: stealth_sync(p))
    return context
