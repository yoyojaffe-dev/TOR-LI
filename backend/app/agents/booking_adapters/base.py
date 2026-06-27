"""Booking adapter interface + shared fill/submit helper.

An adapter knows how to drive one booking platform's form on an already-loaded
Playwright page. The orchestrator (``booking_agent.py``) handles slot lookup,
browser launch, navigation, and render wait, then hands the live ``page`` to the
selected adapter's :meth:`BookingAdapter.submit`.

``fill_and_submit`` is the common tail every adapter uses: fill the mapped
fields, and — only when ``live`` — click submit and verify a confirmation
keyword. When ``live`` is False it is a dry run (no click), so testing can never
create a real appointment.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Page load budget per URL.
PAGE_TIMEOUT_MS = 20_000

# Extra wait after DOMContentLoaded for JS-rendered booking widgets.
RENDER_WAIT_MS = 2_500

# Wait after submitting before reading the confirmation.
CONFIRM_WAIT_MS = 3_000

# Form-HTML budget sent to OpenAI — keeps the mapping prompt cheap.
MAX_HTML_CHARS = 12_000

# Default confirmation signals if an adapter declares none (Hebrew + English).
DEFAULT_CONFIRMATION_KEYWORDS = ["אישור", "נקבע", "הזמנה", "confirmed", "booked", "thank"]

# A field to fill: a CSS selector and the value to type into it.
Field = dict[str, str]


class BookingAdapter(ABC):
    """Drives one booking platform's form on a loaded page."""

    platform: str = "base"

    @abstractmethod
    async def submit(
        self,
        page: Page,
        ctx: dict[str, Any],
        customer_name: str,
        customer_phone: str,
        *,
        live: bool,
    ) -> dict[str, Any]:
        """Fill + (if ``live``) submit the booking on ``page``.

        ``ctx`` is the slot context from ``_fetch_slot_context`` (id, slot_time,
        barbershops{...}). Returns the ``{"success": bool, ...}`` contract.
        """
        raise NotImplementedError


async def fill_and_submit(
    page: Page,
    fields: list[Field],
    submit_selector: str | None,
    confirmation_keywords: list[str] | None,
    *,
    live: bool,
    slot_id: str,
    platform: str,
) -> dict[str, Any]:
    """Fill ``fields`` then, when ``live``, click submit and verify confirmation."""
    for field in fields:
        selector = field.get("selector")
        value = field.get("value")
        if selector and value is not None:
            await page.fill(selector, value)

    if not live:
        logger.info("Dry run (BOOKING_LIVE=false): filled %s form, skipped submit", platform)
        return {"success": True, "dry_run": True, "slot_id": slot_id, "platform": platform}

    if not submit_selector:
        return {
            "success": False,
            "slot_id": slot_id,
            "platform": platform,
            "reason": "no submit selector",
        }

    await page.click(submit_selector)
    await page.wait_for_timeout(CONFIRM_WAIT_MS)

    body = (await page.inner_text("body")).lower()
    keywords = confirmation_keywords or DEFAULT_CONFIRMATION_KEYWORDS
    confirmed = any(kw.lower() in body for kw in keywords)
    logger.info("Submitted %s booking — confirmed=%s", platform, confirmed)
    return {
        "success": confirmed,
        "slot_id": slot_id,
        "platform": platform,
        "confirmed": confirmed,
    }
