"""Profile-extraction layer (foundation).

Runtime-agnostic tooling the future Enrichment runtime will use to extract a
full barbershop profile — staff, per-barber services, and reviews — from two
sources:

* **Booking pages** (free text) → OpenAI function calling via
  ``PROFILE_EXTRACTION_TOOL`` + ``build_profile_messages`` → ``parse_profile``.
* **Google Places** (already structured) → ``external_reviews_from_place``.

This module performs NO I/O (no DB, no OpenAI calls at import) so it is unit
testable in isolation. The agents that actually call OpenAI / write the DB are a
separate phase; ``discovery_agent`` / ``scraping_agent`` import from here when
that lands.
"""

from typing import Any

from app.models.schemas import (
    ExternalReview,
    ExtractedService,
    ExtractedStaff,
    ShopEnrichment,
)

# OpenAI function-calling schema: extract a shop profile from booking-page text.
# Mirrors the shape of SLOT_EXTRACTION_TOOL (scraping_agent) / BOOKING_FORM_TOOL.
PROFILE_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_shop_profile",
        "description": (
            "Extract a men's barbershop profile from its booking-page text: the "
            "team of barbers, the service menu (with category, price, duration, and "
            "which barber offers it when stated), and any customer reviews. Omit "
            "anything not present on the page — never invent data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "staff": {
                    "type": "array",
                    "description": "Barbers / team members listed on the page.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "is_active": {"type": "boolean"},
                        },
                        "required": ["name"],
                    },
                },
                "services": {
                    "type": "array",
                    "description": "Menu items offered.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "category": {
                                "type": "string",
                                "description": "haircut | beard | shave | color | kids | other",
                            },
                            "price": {"type": "number"},
                            "duration_mins": {"type": "integer"},
                            "staff_name": {
                                "type": "string",
                                "description": "Barber who offers it, if the page maps it; else omit.",
                            },
                        },
                        "required": ["name"],
                    },
                },
                "reviews": {
                    "type": "array",
                    "description": "Customer reviews shown on the page.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "author": {"type": "string"},
                            "rating": {"type": "number"},
                            "text": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["staff", "services", "reviews"],
        },
    },
}


def build_profile_messages(shop_name: str, page_text: str) -> list[dict[str, str]]:
    """Build the chat messages that instruct the model to extract the profile."""
    return [
        {
            "role": "system",
            "content": (
                "You extract structured men's-barbershop profiles from booking-page "
                "text (often Hebrew/RTL). Call extract_shop_profile with the team, the "
                "service menu (category, price, duration, and the barber who offers each "
                "when the page says so), and any reviews. Extract every field that is "
                "present; omit what is not — never guess."
            ),
        },
        {
            "role": "user",
            "content": f"Barbershop: {shop_name}\n\nPage content:\n{page_text}",
        },
    ]


def parse_profile(tool_args: dict[str, Any]) -> ShopEnrichment:
    """Validate raw ``extract_shop_profile`` tool-call args into a ShopEnrichment.

    Malformed individual rows raise via Pydantic; missing arrays default to empty.
    """
    return ShopEnrichment(
        staff=[ExtractedStaff(**s) for s in tool_args.get("staff", [])],
        services=[ExtractedService(**s) for s in tool_args.get("services", [])],
        reviews=[ExternalReview(**r) for r in tool_args.get("reviews", [])],
    )


def external_reviews_from_place(place: dict[str, Any]) -> list[ExternalReview]:
    """Map a Google Places detail payload's ``reviews`` to ExternalReview models.

    Google reviews are already structured (author_name, rating, text,
    relative_time_description), so no LLM is needed.
    """
    out: list[ExternalReview] = []
    for r in place.get("reviews") or []:
        out.append(
            ExternalReview(
                author=r.get("author_name"),
                rating=r.get("rating"),
                text=r.get("text"),
                source="google",
                reviewed_at=r.get("relative_time_description"),
            )
        )
    return out
