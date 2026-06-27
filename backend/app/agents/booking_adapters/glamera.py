"""Glamera booking adapter (BOILERPLATE).

Glamera is a salon/beauty booking SaaS used by some barbershops. This adapter
drives its form with static selectors instead of the AI fallback.

The selectors below are PLACEHOLDERS. Verify against the real Glamera DOM once
we have a partner shop / sandbox; until then this adapter is exercised only
against the local fixture (``tests/fixtures/booking/glamera.html``).
"""

from typing import Any

from playwright.async_api import Page

from app.agents.booking_adapters.base import BookingAdapter, fill_and_submit


class GlameraAdapter(BookingAdapter):
    """Static-selector adapter for Glamera booking pages."""

    platform = "glamera"

    # TODO: verify against real Glamera DOM.
    NAME_SELECTOR = "#customer-name"
    PHONE_SELECTOR = "#customer-phone"
    SUBMIT_SELECTOR = "#book-now"
    CONFIRMATION_KEYWORDS = ["booking confirmed", "appointment booked", "אישור", "נקבע"]

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
