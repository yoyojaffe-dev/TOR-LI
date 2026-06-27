"""Tor4You booking adapter (BOILERPLATE).

Tor4You is a common Israeli appointment-booking platform. This adapter drives
its form with static selectors — fast and cheap vs the AI fallback.

The selectors below are PLACEHOLDERS. They must be verified against the real
Tor4You DOM once we have a partner shop / sandbox; until then this adapter is
exercised only against the local fixture (``tests/fixtures/booking/tor4you.html``).
"""

from typing import Any

from playwright.async_api import Page

from app.agents.booking_adapters.base import BookingAdapter, fill_and_submit


class Tor4YouAdapter(BookingAdapter):
    """Static-selector adapter for Tor4You booking pages."""

    platform = "tor4you"

    # TODO: verify against real Tor4You DOM.
    NAME_SELECTOR = "input[name='full_name']"
    PHONE_SELECTOR = "input[name='phone']"
    SUBMIT_SELECTOR = "button[type='submit']"
    CONFIRMATION_KEYWORDS = ["אישור", "נקבע", "התור נקבע", "confirmed"]

    async def submit(
        self,
        page: Page,
        ctx: dict[str, Any],
        customer_name: str,
        customer_phone: str,
        *,
        live: bool,
    ) -> dict[str, Any]:
        fields = [
            {"selector": self.NAME_SELECTOR, "value": customer_name},
            {"selector": self.PHONE_SELECTOR, "value": customer_phone},
        ]
        return await fill_and_submit(
            page,
            fields,
            self.SUBMIT_SELECTOR,
            self.CONFIRMATION_KEYWORDS,
            live=live,
            slot_id=str(ctx.get("id", "")),
            platform=self.platform,
        )
