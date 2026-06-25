"""Discovery Agent (SKELETON).

Scheduled (cron / APScheduler) job that queries the Google Maps Places API for
barbershops within a radius and upserts them into the ``barbershops`` table,
geocoding each into a PostGIS point.

Foundation phase: structure + Supabase contract only. The Google Maps calls are
stubbed and marked TODO for the post-review phase.
"""

from app.config import get_settings
from app.supabase_client import get_supabase


class DiscoveryAgent:
    """Populates ``barbershops`` from Google Maps Places."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_supabase()
        # TODO (Maps phase): self.gmaps = googlemaps.Client(key=self.settings.google_maps_api_key)

    def discover(self, lat: float, lng: float, radius_m: int = 5000) -> int:
        """Search Places near (lat, lng) and upsert results.

        Returns the number of barbershops written. STUB for now.
        """
        # TODO (Maps phase): call gmaps.places_nearby(type="hair_care", ...),
        # page through results, then self._upsert(...) each shop.
        raise NotImplementedError("Discovery Agent: Google Maps integration pending review")

    def _upsert(self, shop: dict) -> None:
        """Upsert a single barbershop row (location set via PostGIS RPC).

        Expected keys: name, address, phone, booking_url, google_place_id, lat, lng.
        """
        self.db.rpc(
            "upsert_barbershop",
            {
                "p_name": shop["name"],
                "p_address": shop.get("address"),
                "p_phone": shop.get("phone"),
                "p_booking_url": shop.get("booking_url"),
                "p_google_place_id": shop.get("google_place_id"),
                "p_lat": shop["lat"],
                "p_lng": shop["lng"],
            },
        ).execute()


def run() -> None:
    """Entry point for the scheduled cron job."""
    # TODO (Maps phase): iterate seed regions and call DiscoveryAgent().discover(...).
    raise NotImplementedError("Discovery Agent cron pending review")
