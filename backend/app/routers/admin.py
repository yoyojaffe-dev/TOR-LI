"""Admin / ops endpoints — development and manual-trigger use only.

Mounted only when ENVIRONMENT != "production".
"""

from fastapi import APIRouter, HTTPException, Query

from app.agents.discovery_agent import DiscoveryAgent

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/discovery/run")
def trigger_discovery(
    lat: float = Query(32.0853, description="Centre latitude (default: Tel Aviv)."),
    lng: float = Query(34.7818, description="Centre longitude (default: Tel Aviv)."),
    radius_m: int = Query(5000, ge=100, le=50000, description="Search radius in metres."),
) -> dict:
    """Trigger one Discovery Agent pass and return the count of shops upserted.

    Example:
        POST /admin/discovery/run?lat=32.0853&lng=34.7818&radius_m=5000
    """
    try:
        count = DiscoveryAgent().discover(lat, lng, radius_m)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "success": True,
        "barbershops_upserted": count,
        "search": {"lat": lat, "lng": lng, "radius_m": radius_m},
    }
