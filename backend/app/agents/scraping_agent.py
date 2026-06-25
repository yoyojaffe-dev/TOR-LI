"""Scraping Agent (SKELETON).

Continuous loop worker:
1. Pull barbershop booking URLs from Supabase.
2. Spin up Playwright, load each booking page, grab the raw HTML.
3. Send the HTML to OpenAI via function-calling to extract times/dates/prices.
4. Upsert the structured results into ``available_slots`` (drives Realtime).

Foundation phase: structure + Supabase contract only. Playwright + OpenAI calls
are stubbed and marked TODO for the post-review phase.
"""

from app.config import get_settings
from app.supabase_client import get_supabase

# OpenAI function-calling schema the parser will use to return structured slots.
SLOT_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_slots",
        "description": "Extract bookable haircut slots from a barber booking page.",
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
                            "slot_time": {"type": "string", "description": "ISO 8601 datetime"},
                        },
                        "required": ["service_name", "slot_time"],
                    },
                }
            },
            "required": ["slots"],
        },
    },
}


class ScrapingAgent:
    """Scrapes barber booking pages and refreshes ``available_slots``."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_supabase()
        # TODO (Playwright phase): init AsyncOpenAI(api_key=...) + Playwright browser.

    def fetch_targets(self) -> list[dict]:
        """Return barbershops that have a booking_url to scrape."""
        res = (
            self.db.table("barbershops")
            .select("id, booking_url")
            .not_.is_("booking_url", "null")
            .execute()
        )
        return res.data or []

    def scrape_page(self, url: str) -> str:
        """Load ``url`` with Playwright and return raw HTML. STUB."""
        # TODO (Playwright phase): browser.new_page(); page.goto(url); return page.content()
        raise NotImplementedError("Scraping Agent: Playwright integration pending review")

    def parse_html(self, html: str) -> list[dict]:
        """Send HTML to OpenAI function-calling, return extracted slots. STUB."""
        # TODO (AI phase): chat.completions with SLOT_EXTRACTION_TOOL, parse tool call args.
        raise NotImplementedError("Scraping Agent: OpenAI parsing pending review")

    def _sync_slots(self, barbershop_id: str, slots: list[dict]) -> None:
        """Upsert extracted slots for a barbershop into ``available_slots``."""
        rows = [
            {
                "barbershop_id": barbershop_id,
                "service_name": s["service_name"],
                "price": s.get("price"),
                "slot_time": s["slot_time"],
                "status": "free",
            }
            for s in slots
        ]
        if rows:
            self.db.table("available_slots").upsert(
                rows, on_conflict="barbershop_id,slot_time,service_name"
            ).execute()


def run() -> None:
    """Entry point for the continuous loop worker."""
    # TODO (Playwright phase): loop fetch_targets -> scrape_page -> parse_html -> _sync_slots.
    raise NotImplementedError("Scraping Agent loop pending review")
