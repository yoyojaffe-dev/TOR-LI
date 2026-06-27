"""Discovery Agent.

Scheduled (cron / APScheduler) job that queries the Google Maps Places API for
barbershops / hair salons within a radius, asks OpenAI to confirm each is a
**men's barbershop**, and upserts the confirmed ones into the ``barbershops``
table, geocoding each into a PostGIS point via the ``upsert_barbershop`` RPC.

Two-stage, async pipeline:
1. **Fetch** (sync ``googlemaps`` SDK, off-loaded via ``asyncio.to_thread``):
   nearby search + Place Details, deduped across place types.
2. **Filter + upsert** (concurrent): each candidate is classified by OpenAI
   (``gpt-4o-mini``, function calling) returning a strict boolean. Non-men's
   shops are skipped (never written). Confirmed shops upsert via the RPC.

Cost note: the Place Details call now also fetches ``reviews`` (a billed Google
"Atmosphere" SKU) to give the classifier real signal, and each candidate costs
one ``gpt-4o-mini`` call. Both are cheap per-shop but add up over a national sweep.

Trigger manually via:
    POST /admin/discovery/run   (FastAPI endpoint — dev only)
    python -m scripts.run_discovery  (standalone script)
"""

import asyncio
import json
import logging
import time
from typing import Any, cast

import googlemaps
from openai import AsyncOpenAI

from app.config import get_settings
from app.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

# Search both Google place types to maximise recall.
_PLACE_TYPES = ["barber_shop", "hair_care"]

# Fields fetched in the Place Details call — minimise billed SKUs.
# ``reviews`` + ``types`` feed the men's-barbershop classifier.
_DETAIL_FIELDS = [
    "place_id",
    "name",
    "formatted_address",
    "formatted_phone_number",
    "website",
    "opening_hours",
    "geometry",
    "photo",
    "reviews",
    # NB: the Place Details request field is the singular "type"; the response
    # still returns the "types" array (read by the men's-barbershop classifier).
    "type",
]

# Max candidates classified+upserted concurrently in one pass. Bounds in-flight
# OpenAI calls + DB writes so a large city can't exhaust rate limits / memory.
_MAX_CONCURRENT_FILTER = 5

# Review-text budget sent to OpenAI — keeps the classifier prompt cheap.
_MAX_REVIEW_CHARS = 4_000

# Private key used to carry the matched place_type alongside each detail dict
# from the fetch stage into the upsert stage.
_PLACE_TYPE_KEY = "_place_type"

MENS_FILTER_TOOL = {
    "type": "function",
    "function": {
        "name": "classify_barbershop",
        "description": (
            "Decide whether a business is a men's barbershop (cuts/grooms men, "
            "including male children). Unisex salons, women's hair salons, beauty "
            "salons, nail/spa places, and non-grooming businesses are NOT men's "
            "barbershops."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "is_mens_barbershop": {
                    "type": "boolean",
                    "description": "True only if this is primarily a men's barbershop.",
                },
                "reason": {
                    "type": "string",
                    "description": "Short justification (for debug logging).",
                },
            },
            "required": ["is_mens_barbershop"],
        },
    },
}


class DiscoveryAgent:
    """Populates ``barbershops`` from Google Maps Places, AI-filtered to men's shops."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = supabase_admin  # service-role: bypasses RLS for direct writes
        self.gmaps = googlemaps.Client(key=self.settings.google_maps_api_key)
        self.openai = AsyncOpenAI(api_key=self.settings.openai_api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def discover(self, lat: float, lng: float, radius_m: int = 5000) -> int:
        """Search Places near (lat, lng), keep men's barbershops, upsert them.

        Returns the number of confirmed men's barbershops written/updated.
        Errors on individual places are logged and skipped, not re-raised.
        """
        candidates = await asyncio.to_thread(self._fetch_candidates, lat, lng, radius_m)
        logger.info("Fetched %d candidate places at (%s, %s)", len(candidates), lat, lng)

        if not candidates:
            return 0

        sem = asyncio.Semaphore(_MAX_CONCURRENT_FILTER)
        results = await asyncio.gather(
            *(self._verify_and_upsert(place, sem) for place in candidates),
            return_exceptions=True,
        )

        verified = 0
        for result in results:
            if isinstance(result, BaseException):
                logger.error("candidate task failed: %s", result)
                continue
            if result:
                verified += 1

        logger.info(
            "Discovery complete: %d candidates → %d men's barbershops upserted (%d skipped)",
            len(candidates),
            verified,
            len(candidates) - verified,
        )
        return verified

    # ------------------------------------------------------------------
    # Stage 1 — fetch (sync; called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _fetch_candidates(self, lat: float, lng: float, radius_m: int) -> list[dict[str, Any]]:
        """Fetch + dedup Place Details across both place types.

        Each returned dict is a Place Details payload tagged with the matched
        place type under ``_PLACE_TYPE_KEY``. No DB writes happen here.
        """
        candidates: list[dict[str, Any]] = []
        seen_place_ids: set[str] = set()

        for place_type in _PLACE_TYPES:
            logger.info("Searching type=%s at (%s, %s) r=%sm", place_type, lat, lng, radius_m)
            response = self.gmaps.places_nearby(
                location=(lat, lng),
                radius=radius_m,
                type=place_type,
            )

            while True:
                for place in response.get("results", []):
                    place_id = place.get("place_id")
                    if not place_id or place_id in seen_place_ids:
                        continue
                    seen_place_ids.add(place_id)

                    try:
                        details = self._get_details(place_id)
                        details[_PLACE_TYPE_KEY] = place_type
                        candidates.append(details)
                    except Exception as exc:
                        logger.error("Skipping %s: %s", place_id, exc)

                next_token = response.get("next_page_token")
                if not next_token:
                    break
                # Google requires a short delay before a next_page_token becomes valid.
                time.sleep(2)
                response = self.gmaps.places_nearby(page_token=next_token)

        return candidates

    def _get_details(self, place_id: str) -> dict[str, Any]:
        """Fetch full Place Details for one place_id."""
        result = self.gmaps.place(place_id, fields=_DETAIL_FIELDS)
        return cast(dict[str, Any], result.get("result", {}))

    # ------------------------------------------------------------------
    # Stage 2 — AI filter + upsert (concurrent)
    # ------------------------------------------------------------------

    async def _verify_and_upsert(self, place: dict[str, Any], sem: asyncio.Semaphore) -> bool:
        """Classify one candidate; upsert it only if it's a men's barbershop.

        Returns True when the shop was written. Bounded by ``sem``.
        """
        async with sem:
            is_mens = await self._is_mens_barbershop(place)

        if not is_mens:
            logger.debug("Skipped (not men's): %s", place.get("name"))
            return False

        place_type = place.get(_PLACE_TYPE_KEY, "barber_shop")
        await asyncio.to_thread(self._upsert, place, place_type)
        logger.debug("Upserted men's barbershop: %s", place.get("name"))
        return True

    async def _is_mens_barbershop(self, place: dict[str, Any]) -> bool:
        """Ask OpenAI whether ``place`` is a men's barbershop.

        Fails closed: any error (API failure, malformed tool call) returns False
        so dubious places are skipped rather than wrongly written.
        """
        name = place.get("name") or "Unknown"
        address = place.get("formatted_address") or ""
        types = ", ".join(place.get("types") or [])
        reviews_text = " ".join(
            r.get("text", "") for r in (place.get("reviews") or []) if r.get("text")
        )[:_MAX_REVIEW_CHARS]

        try:
            response = await self.openai.chat.completions.create(  # type: ignore[call-overload]
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You classify businesses for a men's haircut booking app. "
                            "Decide if the business is a men's barbershop. Reviews may be "
                            "in Hebrew. Call the classify_barbershop function with a strict "
                            "boolean."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Name: {name}\n"
                            f"Address: {address}\n"
                            f"Google types: {types}\n\n"
                            f"Reviews:\n{reviews_text}"
                        ),
                    },
                ],
                tools=[MENS_FILTER_TOOL],
                tool_choice={"type": "function", "function": {"name": "classify_barbershop"}},
            )
            tool_call = response.choices[0].message.tool_calls[0]
            args = json.loads(tool_call.function.arguments)
        except Exception as exc:
            logger.warning("Classifier failed for %s: %s — skipping", name, exc)
            return False

        return bool(args.get("is_mens_barbershop", False))

    # ------------------------------------------------------------------
    # Upsert (sync; called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _upsert(self, place: dict[str, Any], place_type: str = "barber_shop") -> None:
        """Write one barbershop to Supabase via the upsert_barbershop RPC.

        After the RPC, a separate UPDATE stores opening_hours (the RPC does
        not carry that column to keep its signature stable).
        """
        loc = place.get("geometry", {}).get("location", {})
        lat = loc.get("lat")
        lng = loc.get("lng")
        if lat is None or lng is None:
            logger.warning("No geometry for %s — skipped", place.get("name"))
            return

        place_id = place.get("place_id")
        name = place.get("name") or "Unknown"
        address = place.get("formatted_address")
        phone = place.get("formatted_phone_number")
        website = place.get("website")

        # Build photo URLs from up to 6 Places photo references.
        key = self.settings.google_maps_api_key
        photos = place.get("photos") or []
        photo_urls: list[str] = []
        for ph in photos[:6]:
            ref = ph.get("photo_reference")
            if ref:
                photo_urls.append(
                    f"https://maps.googleapis.com/maps/api/place/photo"
                    f"?maxwidth=800&photo_reference={ref}&key={key}"
                )
        photo_url = photo_urls[0] if photo_urls else None

        # Upsert core row + PostGIS point via RPC.
        self.db.rpc(
            "upsert_barbershop",
            {
                "p_name": name,
                "p_lat": lat,
                "p_lng": lng,
                "p_address": address,
                "p_phone": phone,
                "p_booking_url": website,
                "p_google_place_id": place_id,
                "p_photo_url": photo_url,
                "p_place_type": place_type,
                "p_photo_urls": photo_urls,
                "p_rating": place.get("rating"),
                "p_rating_count": place.get("user_ratings_total"),
            },
        ).execute()

        # Patch opening_hours separately (jsonb column not in the RPC signature).
        if oh_raw := place.get("opening_hours"):
            opening_hours = {
                "weekday_text": oh_raw.get("weekday_text", []),
                "periods": oh_raw.get("periods", []),
                "open_now": oh_raw.get("open_now"),
            }
            if place_id:
                self.db.table("barbershops").update({"opening_hours": opening_hours}).eq(
                    "google_place_id", place_id
                ).execute()


# ---------------------------------------------------------------------------
# Module-level entry points
# ---------------------------------------------------------------------------


def run(lat: float = 32.0853, lng: float = 34.7818, radius_m: int = 5000) -> int:
    """Run one discovery pass and return the count of shops upserted."""
    return asyncio.run(DiscoveryAgent().discover(lat, lng, radius_m))
