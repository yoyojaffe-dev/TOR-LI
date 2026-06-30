"""Scraping Agent.

Continuous async loop:
1. Pull barbershop booking URLs from Supabase.
2. Load each URL with headless Playwright Chromium; extract visible text.
3. Send text to OpenAI (gpt-4o-mini, function-calling) to extract slots.
4. Upsert extracted slots into available_slots via upsert_free_slot RPC
   (never resets a locked/booked slot back to free).

Trigger manually via:
    POST /admin/scraping/run        (one pass, async background task)
    python -m scripts.run_scraping  (blocking loop)
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

from openai import AsyncOpenAI
from playwright.async_api import Browser, async_playwright

from app.config import get_settings
from app.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

# Visible-text budget sent to OpenAI — keeps prompt tokens cheap.
_MAX_TEXT_CHARS = 15_000

# Page load budget per URL.
_PAGE_TIMEOUT_MS = 20_000

# Extra wait after DOMContentLoaded for JS-rendered booking widgets.
_RENDER_WAIT_MS = 2_500

# Default seconds between full scraping passes.
LOOP_INTERVAL_SECONDS = 300

# Max shops scraped concurrently in one pass. Bounds open browser contexts +
# OpenAI calls so a large target list can't exhaust memory / rate limits.
_MAX_CONCURRENT_SHOPS = 5

# Domains that require auth or block headless browsers — skip them.
_SKIP_DOMAINS = {"facebook.com", "instagram.com", "twitter.com", "t.me"}

SLOT_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_slots",
        "description": "Extract bookable haircut appointment slots from a barber booking page.",
        "parameters": {
            "type": "object",
            "properties": {
                "slots": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "service_name": {"type": "string"},
                            "price": {"type": "number"},
                            "slot_time": {
                                "type": "string",
                                "description": "ISO 8601 datetime with timezone offset, e.g. 2026-06-25T14:00:00+03:00",
                            },
                        },
                        "required": ["service_name", "slot_time"],
                    },
                }
            },
            "required": ["slots"],
        },
    },
}


def _is_skippable_url(url: str) -> bool:
    """True for social/auth-walled URLs we can't headlessly scrape."""
    return any(domain in url for domain in _SKIP_DOMAINS)


class ScrapingAgent:
    """Scrapes barbershop booking pages and syncs available_slots."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = supabase_admin  # service-role: bypasses RLS
        self.openai = AsyncOpenAI(api_key=self.settings.openai_api_key)

    # ------------------------------------------------------------------
    # Supabase (sync, called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def fetch_targets(self) -> list[dict[str, Any]]:
        """Return barbershops with a scrappable booking_url."""
        res = (
            self.db.table("barbershops")
            .select("id, name, booking_url")
            .not_.is_("booking_url", "null")
            # Don't waste scrape/OpenAI cycles on non-barbershops — same
            # place_type restriction the consumer barbershops_within_radius RPC
            # applies, so only real barbers reach the scraping pipeline.
            .in_("place_type", ["barber_shop", "hair_care"])
            .execute()
        )
        return [
            shop for shop in (res.data or []) if not _is_skippable_url(shop.get("booking_url", ""))
        ]

    def _sync_slots(self, barbershop_id: str, slots: list[dict[str, Any]]) -> int:
        """Upsert slots via upsert_free_slot RPC. Returns count written."""
        written = 0
        for slot in slots:
            try:
                self.db.rpc(
                    "upsert_free_slot",
                    {
                        "p_barbershop_id": barbershop_id,
                        "p_service_name": slot["service_name"],
                        "p_slot_time": slot["slot_time"],
                        "p_price": slot.get("price"),
                    },
                ).execute()
                written += 1
            except Exception as exc:
                logger.warning("slot upsert failed for %s: %s", barbershop_id, exc)
        return written

    # ------------------------------------------------------------------
    # Playwright
    # ------------------------------------------------------------------

    async def scrape_page(self, browser: Browser, url: str) -> str:
        """Load url headlessly and return visible body text, truncated."""
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            viewport={"width": 390, "height": 844},
            locale="he-IL",
        )
        page = await context.new_page()
        try:
            await page.goto(url, timeout=_PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_timeout(_RENDER_WAIT_MS)
            text = await page.inner_text("body")
            return text[:_MAX_TEXT_CHARS]
        finally:
            await context.close()

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------

    async def parse_html(self, text: str, shop_name: str) -> list[dict[str, Any]]:
        """Send visible page text to OpenAI; return extracted slot dicts."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        response = await self.openai.chat.completions.create(  # type: ignore[call-overload]
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Today is {today}. "
                        "Extract bookable haircut appointment slots from barbershop website text. "
                        "Return ISO 8601 datetimes with timezone offset (+03:00 for Israel). "
                        "If no specific slots are visible, return an empty list."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Barbershop: {shop_name}\n\nPage content:\n{text}",
                },
            ],
            tools=[SLOT_EXTRACTION_TOOL],
            tool_choice={"type": "function", "function": {"name": "extract_slots"}},
        )
        tool_call = response.choices[0].message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        return cast(list[dict[str, Any]], args.get("slots", []))

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def process_shop(self, browser: Browser, shop: dict[str, Any]) -> int:
        """Scrape one shop and sync its slots. Returns slot count written."""
        shop_id = shop["id"]
        name = shop.get("name", "Unknown")
        url = shop["booking_url"]

        try:
            text = await self.scrape_page(browser, url)
            logger.debug("%s: scraped %d chars from %s", name, len(text), url)

            slots = await self.parse_html(text, name)
            logger.info("%s: OpenAI extracted %d slots", name, len(slots))

            if not slots:
                return 0

            written = await asyncio.to_thread(self._sync_slots, shop_id, slots)
            logger.info("%s: %d slots written to DB", name, written)
            return written

        except Exception as exc:
            logger.error("Error processing %s (%s): %s", name, url, exc)
            return 0

    async def run_once(self) -> dict[str, int]:
        """One full pass: fetch targets -> scrape -> parse -> sync. Returns stats.

        Shops are processed concurrently (bounded by ``_MAX_CONCURRENT_SHOPS``)
        since each is independent and I/O-bound. A semaphore caps the number of
        simultaneously-open browser contexts and in-flight OpenAI calls.
        """
        targets = await asyncio.to_thread(self.fetch_targets)
        logger.info("Scraping pass: %d targets", len(targets))

        stats: dict[str, int] = {"shops_processed": 0, "slots_written": 0}
        if not targets:
            return stats

        sem = asyncio.Semaphore(_MAX_CONCURRENT_SHOPS)

        async def _guarded(shop: dict[str, Any]) -> int:
            async with sem:
                return await self.process_shop(browser, shop)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                results = await asyncio.gather(
                    *(_guarded(shop) for shop in targets),
                    return_exceptions=True,
                )
            finally:
                await browser.close()

        for result in results:
            stats["shops_processed"] += 1
            if isinstance(result, BaseException):
                # process_shop already isolates its own errors; this is a
                # last-resort guard so one task can't sink the whole pass.
                logger.error("shop task failed: %s", result)
                continue
            stats["slots_written"] += result

        return stats

    async def run(self, interval: int = LOOP_INTERVAL_SECONDS) -> None:
        """Continuous loop — awaited from main.py lifespan. Runs until cancelled."""
        logger.info("Scraping Agent loop started (interval=%ds)", interval)
        while True:
            try:
                stats = await self.run_once()
                logger.info("Pass done: %s", stats)
            except asyncio.CancelledError:
                logger.info("Scraping Agent loop cancelled")
                raise
            except Exception as exc:
                logger.error("Pass failed: %s", exc)
            await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# Module-level entry points
# ---------------------------------------------------------------------------


async def run_once() -> dict[str, int]:
    return await ScrapingAgent().run_once()


def run(interval: int = LOOP_INTERVAL_SECONDS) -> None:
    """Blocking entry point for the standalone script."""
    asyncio.run(ScrapingAgent().run(interval))
