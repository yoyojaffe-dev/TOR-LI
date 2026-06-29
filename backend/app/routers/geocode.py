"""Geocoding helper: free-text address -> lat/lng via the Google Maps SDK.

Runs server-side so the Maps API key is never exposed to the browser. The barber
dashboard calls this when a shop's address is edited, then writes the returned
coordinates into ``barbershops.location`` so the map pin and the location-based
nearby search stay in sync.
"""

from typing import Annotated, Any, cast

import googlemaps
from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.models.schemas import GeocodeResult

router = APIRouter(tags=["geo"])


@router.get("/geocode", response_model=GeocodeResult)
def geocode(
    address: Annotated[str, Query(min_length=1, description="Free-text address to geocode.")],
) -> GeocodeResult:
    settings = get_settings()
    if not settings.google_maps_api_key:
        raise HTTPException(status_code=503, detail="geocoding is not configured")
    client = googlemaps.Client(key=settings.google_maps_api_key)
    results = cast(list[dict[str, Any]], client.geocode(address))
    if not results:
        raise HTTPException(status_code=404, detail="address not found")
    top = results[0]
    loc = top["geometry"]["location"]
    return GeocodeResult(
        lat=float(loc["lat"]),
        lng=float(loc["lng"]),
        formatted_address=top.get("formatted_address"),
    )
