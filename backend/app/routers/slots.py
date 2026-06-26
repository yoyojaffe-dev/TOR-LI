"""Available slot listing.

Slots belong to a barbershop and are referenced by bookings. The Scraping Agent
keeps ``available_slots`` fresh; the frontend gets live updates directly from
Supabase Realtime (this REST route is the initial-load / fallback path).
"""

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import NearbySlot, Slot, SlotStatus
from app.services import locking
from app.supabase_client import get_supabase

router = APIRouter(prefix="/slots", tags=["slots"])

# Frontend subscribes to this Realtime channel for live slot pushes.
REALTIME_CHANNEL = "public:available_slots"


@router.get("", response_model=list[Slot])
def list_slots(
    barbershop_id: str = Query(..., description="Barbershop to list slots for."),
    only_free: bool = Query(True, description="Exclude locked/booked slots."),
) -> list[Slot]:
    """Return upcoming slots for a barbershop, soonest first."""
    query = (
        get_supabase()
        .table("available_slots")
        .select("*")
        .eq("barbershop_id", barbershop_id)
        .order("slot_time")
    )
    if only_free:
        query = query.eq("status", SlotStatus.free.value)

    res = query.execute()
    return [Slot(**row) for row in (res.data or [])]


@router.get("/nearby", response_model=list[NearbySlot])
def list_nearby_slots(
    lat: float = Query(..., description="User latitude (WGS84)."),
    lng: float = Query(..., description="User longitude (WGS84)."),
    radius: int = Query(5000, ge=1, le=50000, description="Search radius in metres."),
    limit: int = Query(20, ge=1, le=100, description="Max slots to return."),
) -> list[NearbySlot]:
    """Return free upcoming slots near a point, joined to shop info, nearest first."""
    try:
        rows = locking.nearby_slots(lat, lng, radius, limit)
    except Exception as exc:  # surface DB/RPC errors as 502
        raise HTTPException(status_code=502, detail=f"nearby query failed: {exc}") from exc

    return [NearbySlot(**row) for row in rows]


@router.get("/realtime-info")
def realtime_info() -> dict:
    """Expose the channel + table the frontend should subscribe to."""
    return {"channel": REALTIME_CHANNEL, "table": "available_slots", "schema": "public"}
