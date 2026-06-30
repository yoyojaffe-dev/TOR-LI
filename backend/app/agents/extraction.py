"""Profile-extraction layer.

Tooling the Enrichment runtime uses to extract a full barbershop profile —
staff, per-barber services, and reviews — plus the guardrails that keep the
output trustworthy:

* **Booking pages** (free text) → OpenAI function calling via
  ``PROFILE_EXTRACTION_TOOL`` + ``build_profile_messages`` → ``parse_profile``.
* **Google Places** (already structured) → ``external_reviews_from_place``.

Guards (all pure / unit-tested): ``is_content_sufficient`` (skip thin pages),
a hard-negative instruction baked into the tool + prompt, ``filter_reviews``
(drop anonymous / empty reviews), and ``is_pricing_source`` (only trust
price/duration from known booking platforms).

This module performs NO I/O (no DB, no OpenAI calls at import) so it is unit
testable in isolation.
"""

from typing import Any
from urllib.parse import urlparse

from app.agents.booking_adapters.detect import detect_platform
from app.models.schemas import (
    ExternalReview,
    ExtractedService,
    ExtractedStaff,
    ShopEnrichment,
)

# Pages shorter than this (visible text) are app-walls / redirects / errors —
# extracting from them only invites hallucination, so we skip them entirely.
MIN_CONTENT_LENGTH = 200

# Platforms whose pages we trust for price/duration. Generic/marketing pages
# list service names but rarely real prices, so we null those out.
_PRICING_PLATFORMS = {"tor4you", "glamera", "calmark", "eztor", "cutshave"}

# Authors that signal a non-attributable review — dropped to keep the table clean.
_GENERIC_AUTHORS = ("anonymous", "אנונימי", "google user", "a google user", "משתמש")

# Reused in the tool description and the system prompt so the model is told, in
# both places, never to fabricate entities.
_HARD_NEGATIVE = (
    "If a staff name or service is not explicitly visible in the text you MUST omit "
    "it (return null / leave it out). Never invent staff, services, or reviews — "
    "fabricated data fails the system. (You SHOULD still classify each service that "
    "IS listed into a category from its name — that inference is expected, not "
    "invention.)"
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
            "which barber offers it when stated), and any customer reviews. " + _HARD_NEGATIVE
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
                "when the page says so), and any reviews. " + _HARD_NEGATIVE
            ),
        },
        {
            "role": "user",
            "content": f"Barbershop: {shop_name}\n\nPage content:\n{page_text}",
        },
    ]


def is_content_sufficient(page_text: str) -> bool:
    """True if the page has enough visible text to be worth extracting from.

    Guards against app-walls / redirects / error pages that yield only a banner.
    """
    return len(page_text.strip()) >= MIN_CONTENT_LENGTH


def is_pricing_source(url: str | None) -> bool:
    """True only for booking platforms whose pages we trust for price/duration.

    Generic / marketing pages list service names but rarely real prices, so the
    runtime nulls price/duration for them.
    """
    if not url or not urlparse(url).hostname:
        return False
    return detect_platform(url) in _PRICING_PLATFORMS


def _is_generic_author(author: str | None) -> bool:
    if not author or not author.strip():
        return True
    low = author.strip().lower()
    return any(marker in low for marker in _GENERIC_AUTHORS)


def filter_reviews(reviews: list[ExternalReview]) -> list[ExternalReview]:
    """Drop low-quality reviews: empty text, rating-without-text, generic authors."""
    kept: list[ExternalReview] = []
    for r in reviews:
        if not r.text or not r.text.strip():
            continue  # empty text / rating-only
        if _is_generic_author(r.author):
            continue
        kept.append(r)
    return kept


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
