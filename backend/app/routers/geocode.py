"""Address -> coordinates geocoding (authenticated barbers only).

Onboarding turns the free-text address a barber types into a PostGIS point. This
wraps the Google Maps Geocoding API (the same key the Discovery Agent uses)
behind the barber auth gate, so it works in production without exposing billed
geocoding to the open public. Mounted unconditionally (unlike the admin router),
because onboarding runs in production.
"""

from typing import Annotated

import googlemaps
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.config import get_settings
from app.dependencies import get_authed_supabase
from app.models.schemas import GeocodeResult

router = APIRouter(prefix="/geocode", tags=["geocode"])

# Require an authenticated barber session (same dependency the booking routes use).
AuthedClient = Annotated[Client, Depends(get_authed_supabase)]


@router.get("", response_model=GeocodeResult)
def geocode(
    _client: AuthedClient,
    address: Annotated[str, Query(min_length=1, description="Free-text address to resolve.")],
) -> GeocodeResult:
    """Resolve ``address`` to ``{lat, lng}`` via Google. 404 when unresolvable."""
    settings = get_settings()
    if not settings.google_maps_api_key:
        raise HTTPException(status_code=503, detail="geocoding not configured")

    gmaps = googlemaps.Client(key=settings.google_maps_api_key)
    try:
        results = gmaps.geocode(address, region="il")
    except Exception as exc:  # network / Google API errors -> 502
        raise HTTPException(status_code=502, detail=f"geocoding failed: {exc}") from exc

    if not results:
        raise HTTPException(status_code=404, detail="address not found")

    loc = results[0]["geometry"]["location"]
    return GeocodeResult(lat=loc["lat"], lng=loc["lng"])
