"""Booking Agent.

On-demand worker triggered by POST /bookings/confirm. It navigates to the
original barber's booking site with headless Playwright, then delegates the
form fill + submit to a platform-specific adapter (Tor4You, Glamera, …),
falling back to AI form-mapping for unknown/custom sites.

Flow:
1. Look up the slot's barbershop booking_url + slot_time / service_name.
2. Load the page (headless Chromium) and wait for JS widgets to render.
3. Pick an adapter from the booking_url (``booking_adapters.get_adapter``).
4. The adapter fills the form and — when ``settings.booking_live`` is True —
   clicks submit and verifies a confirmation keyword. Default is a dry run
   (fill, no submit), so testing can't create real appointments.

Returns the ``{"success": bool, ...}`` contract the router checks: on failure
the caller releases the lock and returns HTTP 502.
"""

import asyncio
import logging
from typing import Any

from openai import AsyncOpenAI
from playwright.async_api import Browser, async_playwright

from app.agents.booking_adapters import get_adapter
from app.agents.booking_adapters.base import PAGE_TIMEOUT_MS, RENDER_WAIT_MS
from app.agents.scraping_agent import _is_skippable_url
from app.config import get_settings
from app.supabase_client import one_row, supabase_admin

logger = logging.getLogger(__name__)


class BookingAgent:
    """Submits a reservation on the barber's own booking site."""

    def __init__(self) -> None:
        self.settings = get_settings()
        # Service-role client: background agents bypass RLS to write directly.
        self.db = supabase_admin
        self.openai = AsyncOpenAI(api_key=self.settings.openai_api_key)

    # ------------------------------------------------------------------
    # Supabase (sync, called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _fetch_slot_context(self, slot_id: str) -> dict[str, Any]:
        """Return slot detail joined to its barbershop, or {} if not found."""
        res = (
            self.db.table("available_slots")
            .select("id, service_name, slot_time, barbershops(name, booking_url)")
            .eq("id", slot_id)
            .limit(1)
            .execute()
        )
        return one_row(res.data)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def submit(self, slot_id: str, customer_name: str, customer_phone: str) -> dict[str, Any]:
        """Submit the booking for ``slot_id``. See module docstring for the flow."""
        ctx = await asyncio.to_thread(self._fetch_slot_context, slot_id)
        if not ctx:
            return {"success": False, "slot_id": slot_id, "reason": "slot not found"}

        shop = ctx.get("barbershops") or {}
        url = shop.get("booking_url")
        if not url:
            return {"success": False, "slot_id": slot_id, "reason": "no booking_url"}
        if _is_skippable_url(url):
            return {"success": False, "slot_id": slot_id, "reason": "unsupported booking site"}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                return await self._book_on_page(browser, url, ctx, customer_name, customer_phone)
            except Exception as exc:
                logger.error("Booking failed for slot %s (%s): %s", slot_id, url, exc)
                return {"success": False, "slot_id": slot_id, "reason": str(exc)}
            finally:
                await browser.close()

    async def _book_on_page(
        self,
        browser: Browser,
        url: str,
        ctx: dict[str, Any],
        customer_name: str,
        customer_phone: str,
    ) -> dict[str, Any]:
        """Load the booking page, then delegate fill/submit to a platform adapter."""
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
            await page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_timeout(RENDER_WAIT_MS)

            adapter = get_adapter(url, self.openai)
            logger.info("Booking %s via %s adapter", url, adapter.platform)
            return await adapter.submit(
                page,
                ctx,
                customer_name,
                customer_phone,
                live=self.settings.booking_live,
            )
        finally:
            await context.close()


# ---------------------------------------------------------------------------
# Module-level entry point
# ---------------------------------------------------------------------------


async def submit(slot_id: str, customer_name: str, customer_phone: str) -> dict[str, Any]:
    """Run one booking submission."""
    return await BookingAgent().submit(slot_id, customer_name, customer_phone)
