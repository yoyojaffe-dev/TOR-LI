"""Booking adapter validation harness (real Chromium, local fixtures).

Validates per-platform routing + fill/submit WITHOUT any real shop: for each
platform it navigates to a real platform hostname (so ``get_adapter`` detection
fires) but intercepts the request and serves a local fixture page. The selected
adapter then fills + (if BOOKING_LIVE) submits against the fixture, and we check
the confirmation.

Usage (from /backend):
    BOOKING_LIVE=true  python -m scripts.validate_booking   # full live submit path
    BOOKING_LIVE=false python -m scripts.validate_booking   # dry run (no submit click)

Only the "custom" case calls OpenAI (the AI fallback). No network to real sites.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure /backend is on the path when run as `python -m scripts.validate_booking`.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from openai import AsyncOpenAI  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

from app.agents.booking_adapters import get_adapter  # noqa: E402
from app.config import get_settings  # noqa: E402
from scripts._cli import run_safely  # noqa: E402

logger = logging.getLogger("validate_booking")

_FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "booking"

# (expected platform, URL that triggers detection, fixture served for it)
CASES = [
    ("tor4you", "https://book.tor4you.co.il/shop/123", "tor4you.html"),
    ("glamera", "https://app.glamera.com/shop/123", "glamera.html"),
    ("custom", "https://my-barber.example/book", "custom.html"),
]


async def _run_case(pw_browser, openai, platform, url, fixture, *, live) -> bool:  # type: ignore[no-untyped-def]
    html = (_FIXTURES / fixture).read_text(encoding="utf-8")
    context = await pw_browser.new_context(locale="he-IL")
    # Serve the fixture for any request under this case's host.
    await context.route(
        "**/*",
        lambda route: asyncio.create_task(
            route.fulfill(status=200, content_type="text/html", body=html)
        ),
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded")
        adapter = get_adapter(url, openai)
        routed_ok = adapter.platform == platform
        ctx = {"id": f"slot-{platform}", "slot_time": "2026-06-28T10:00:00+03:00"}
        result = await adapter.submit(page, ctx, "דנה בדיקה", "+972501234567", live=live)
        ok = routed_ok and bool(result.get("success"))
        logger.info(
            "%-8s url=%s -> adapter=%s routed=%s result=%s",
            platform,
            url,
            adapter.platform,
            routed_ok,
            result,
        )
        return ok
    finally:
        await context.close()


async def main() -> None:
    settings = get_settings()
    live = settings.booking_live
    openai = AsyncOpenAI(api_key=settings.openai_api_key)
    logger.info("Validating booking adapters (BOOKING_LIVE=%s)", live)

    results: list[tuple[str, bool]] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for platform, url, fixture in CASES:
                ok = await _run_case(browser, openai, platform, url, fixture, live=live)
                results.append((platform, ok))
        finally:
            await browser.close()

    print("\n=== Booking adapter validation ===")
    for platform, ok in results:
        print(f"  {platform:<8} {'PASS' if ok else 'FAIL'}")
    if not all(ok for _, ok in results):
        sys.exit(1)


if __name__ == "__main__":
    run_safely(lambda: asyncio.run(main()))
