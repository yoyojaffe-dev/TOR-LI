"""Generic AI booking adapter — the fallback for unknown/custom sites.

When no platform-specific adapter matches the booking URL, this adapter asks
OpenAI (gpt-4o-mini, function-calling) to map the customer's name/phone onto the
page's form selectors, then fills + (if live) submits. Slower and costlier than
a static adapter, so it is used only as the fallback.
"""

import json
import logging
from typing import Any, cast

from openai import AsyncOpenAI
from playwright.async_api import Page

from app.agents.booking_adapters.base import (
    MAX_HTML_CHARS,
    BookingAdapter,
    fill_and_submit,
)

logger = logging.getLogger(__name__)

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


class GenericAIAdapter(BookingAdapter):
    """Fallback adapter: AI-maps the form for unknown platforms."""

    platform = "custom"

    def __init__(self, openai: AsyncOpenAI) -> None:
        self.openai = openai

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

    async def submit(
        self,
        page: Page,
        ctx: dict[str, Any],
        customer_name: str,
        customer_phone: str,
        *,
        live: bool,
    ) -> dict[str, Any]:
        html = (await page.content())[:MAX_HTML_CHARS]
        slot_time = str(ctx.get("slot_time", ""))
        plan = await self._map_form(html, customer_name, customer_phone, slot_time)
        return await fill_and_submit(
            page,
            plan.get("fields", []),
            plan.get("submit_selector"),
            plan.get("confirmation_keywords"),
            live=live,
            slot_id=str(ctx.get("id", "")),
            platform=self.platform,
        )
