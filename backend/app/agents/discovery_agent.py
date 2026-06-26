"""Discovery Agent.

Scheduled (cron / APScheduler) job that queries the Google Maps Places API for
barbershops / hair salons within a radius and upserts them into the
``barbershops`` table, geocoding each into a PostGIS point via the
``upsert_barbershop`` RPC.

Trigger manually via:
    POST /admin/discovery/run   (FastAPI endpoint — dev only)
    python -m scripts.run_discovery  (standalone script)
"""

import json
import logging
import time

import googlemaps

from app.config import get_settings
from app.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

# Search both Google place types to maximise recall.
_PLACE_TYPES = ["barber_shop", "hair_care"]

# Fields fetched in the Place Details call — minimise billed SKUs.
_DETAIL_FIELDS = [
    "place_id",
    "name",
    "formatted_address",
    "formatted_phone_number",
    "website",
    "opening_hours",
    "geometry",
    "photo",
]


class DiscoveryAgent:
    """Populates ``barbershops`` from Google Maps Places."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = supabase_admin  # service-role: bypasses RLS for direct writes
        self.gmaps = googlemaps.Client(key=self.settings.google_maps_api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(self, lat: float, lng: float, radius_m: int = 5000) -> int:
        """Search Places near (lat, lng) within radius_m and upsert results.

        Returns the total number of barbershops written/updated.
        Errors on individual places are logged and skipped, not re-raised.
        """
        total = 0
        seen_place_ids: set[str] = set()

        for place_type in _PLACE_TYPES:
            logger.info("Searching type=%s at (%s, %s) r=%sm", place_type, lat, lng, radius_m)
            count = self._search_and_upsert(lat, lng, radius_m, place_type, seen_place_ids)
            logger.info("type=%s → %d places written", place_type, count)
            total += count

        logger.info("Discovery complete: %d total barbershops upserted", total)
        return total

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_and_upsert(
        self,
        lat: float,
        lng: float,
        radius_m: int,
        place_type: str,
        seen: set[str],
    ) -> int:
        count = 0
        response = self.gmaps.places_nearby(
            location=(lat, lng),
            radius=radius_m,
            type=place_type,
        )

        while True:
            for place in response.get("results", []):
                place_id = place.get("place_id")
                if not place_id or place_id in seen:
                    continue
                seen.add(place_id)

                try:
                    details = self._get_details(place_id)
                    self._upsert(details, place_type)
                    count += 1
                    logger.debug("Upserted: %s (%s)", details.get("name"), place_id)
                except Exception as exc:
                    logger.error("Skipping %s: %s", place_id, exc)

            next_token = response.get("next_page_token")
            if not next_token:
                break
            # Google requires a short delay before a next_page_token becomes valid.
            time.sleep(2)
            response = self.gmaps.places_nearby(page_token=next_token)

        return count

    def _get_details(self, place_id: str) -> dict:
        """Fetch full Place Details for one place_id."""
        result = self.gmaps.place(place_id, fields=_DETAIL_FIELDS)
        return result.get("result", {})

    def _upsert(self, place: dict, place_type: str = "barber_shop") -> None:
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
                self.db.table("barbershops").update(
                    {"opening_hours": opening_hours}
                ).eq("google_place_id", place_id).execute()


# ---------------------------------------------------------------------------
# Module-level entry points
# ---------------------------------------------------------------------------

def run(lat: float = 32.0853, lng: float = 34.7818, radius_m: int = 5000) -> int:
    """Run one discovery pass and return the count of shops upserted."""
    return DiscoveryAgent().discover(lat, lng, radius_m)
