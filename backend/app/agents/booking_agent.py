"""Booking Agent.

On-demand worker triggered by POST /bookings/confirm. It navigates to the
original barber's booking site with headless Playwright, uses OpenAI
function-calling to map the customer's name + phone onto the page's form
fields, fills them, submits, and verifies the confirmation.

Flow:
1. Look up the slot's barbershop booking_url + slot_time / service_name.
2. Load the page (headless Chromium), grab the form HTML.
3. Ask OpenAI (gpt-4o-mini, function-calling) for the CSS selectors to fill
   and the submit button selector.
4. Fill the fields. If ``settings.booking_live`` is True, click submit and
   verify a confirmation keyword; otherwise return a dry-run result without
   submitting (kill-switch so testing can't create real appointments).

Returns the ``{"success": bool, ...}`` contract the router checks: on failure
the caller releases the lock and returns HTTP 502.
"""

import asyncio
import json
import logging
from typing import Any, cast

from openai import AsyncOpenAI
from playwright.async_api import Browser, async_playwright

from app.agents.scraping_agent import _is_skippable_url
from app.config import get_settings
from app.supabase_client import one_row, supabase_admin

logger = logging.getLogger(__name__)

# Page load budget per URL.
_PAGE_TIMEOUT_MS = 20_000

# Extra wait after DOMContentLoaded for JS-rendered booking widgets.
_RENDER_WAIT_MS = 2_500

# Wait after submitting before reading the confirmation.
_CONFIRM_WAIT_MS = 3_000

# Form-HTML budget sent to OpenAI — keeps the mapping prompt cheap.
_MAX_HTML_CHARS = 12_000

# Default confirmation signals if the model returns none (Hebrew + English).
_DEFAULT_CONFIRMATION_KEYWORDS = ["אישור", "נקבע", "הזמנה", "confirmed", "booked", "thank"]

BOOKING_FORM_TOOL = {
    "type": "function",
    "function": {
        "name": "fill_booking_form",
        "description": (
            "Map a customer's name and phone onto a barber booking page's form. "
            "Return the CSS selectors to fill and the submit button selector."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "description": "Form inputs to fill, in order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "selector": {
                                "type": "string",
                                "description": "CSS selector for the input element.",
                            },
                            "value": {
                                "type": "string",
                                "description": "Value to type into it.",
                            },
                        },
                        "required": ["selector", "value"],
                    },
                },
                "submit_selector": {
                    "type": "string",
                    "description": "CSS selector for the submit/confirm button.",
                },
                "confirmation_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Text snippets that appear once the booking succeeds.",
                },
            },
            "required": ["fields", "submit_selector"],
        },
    },
}


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
    # OpenAI
    # ------------------------------------------------------------------

    async def _map_form(
        self, html: str, customer_name: str, customer_phone: str, slot_time: str
    ) -> dict[str, Any]:
        """Ask OpenAI for the selectors to fill + the submit button selector."""
        response = await self.openai.chat.completions.create(  # type: ignore[call-overload]
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You automate barbershop booking forms (often Hebrew/RTL). "
                        "Given the page HTML and the customer's details, return precise "
                        "CSS selectors for the name and phone inputs and the submit button."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Customer name: {customer_name}\n"
                        f"Customer phone: {customer_phone}\n"
                        f"Desired slot time: {slot_time}\n\n"
                        f"Page HTML:\n{html}"
                    ),
                },
            ],
            tools=[BOOKING_FORM_TOOL],
            tool_choice={"type": "function", "function": {"name": "fill_booking_form"}},
        )
        tool_call = response.choices[0].message.tool_calls[0]
        return cast(dict[str, Any], json.loads(tool_call.function.arguments))

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

        slot_time = str(ctx.get("slot_time", ""))

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                return await self._book_on_page(
                    browser, url, slot_id, customer_name, customer_phone, slot_time
                )
            except Exception as exc:
                logger.error("Booking failed for slot %s (%s): %s", slot_id, url, exc)
                return {"success": False, "slot_id": slot_id, "reason": str(exc)}
            finally:
                await browser.close()

    async def _book_on_page(
        self,
        browser: Browser,
        url: str,
        slot_id: str,
        customer_name: str,
        customer_phone: str,
        slot_time: str,
    ) -> dict[str, Any]:
        """Load the booking page, fill the form, and (if live) submit it."""
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
            html = (await page.content())[:_MAX_HTML_CHARS]

            plan = await self._map_form(html, customer_name, customer_phone, slot_time)
            for field in plan.get("fields", []):
                selector = field.get("selector")
                value = field.get("value")
                if selector and value is not None:
                    await page.fill(selector, value)

            submit_selector = plan.get("submit_selector")

            if not self.settings.booking_live:
                logger.info("Dry run (BOOKING_LIVE=false): filled form, skipped submit for %s", url)
                return {"success": True, "dry_run": True, "slot_id": slot_id}

            if not submit_selector:
                return {"success": False, "slot_id": slot_id, "reason": "no submit selector"}

            await page.click(submit_selector)
            await page.wait_for_timeout(_CONFIRM_WAIT_MS)

            body = (await page.inner_text("body")).lower()
            keywords = plan.get("confirmation_keywords") or _DEFAULT_CONFIRMATION_KEYWORDS
            confirmed = any(kw.lower() in body for kw in keywords)
            logger.info("Submitted booking for %s — confirmed=%s", url, confirmed)
            return {"success": confirmed, "slot_id": slot_id, "confirmed": confirmed}
        finally:
            await context.close()


# ---------------------------------------------------------------------------
# Module-level entry point
# ---------------------------------------------------------------------------


async def submit(slot_id: str, customer_name: str, customer_phone: str) -> dict[str, Any]:
    """Run one booking submission."""
    return await BookingAgent().submit(slot_id, customer_name, customer_phone)
