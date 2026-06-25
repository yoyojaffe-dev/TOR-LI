"""Available slot listing.

Slots belong to a barbershop and are referenced by bookings. The Scraping Agent
keeps ``available_slots`` fresh; the frontend gets live updates directly from
Supabase Realtime (this REST route is the initial-load / fallback path).
"""

from fastapi import APIRouter, Query

from app.models.schemas import Slot, SlotStatus
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


@router.get("/realtime-info")
def realtime_info() -> dict:
    """Expose the channel + table the frontend should subscribe to."""
    return {"channel": REALTIME_CHANNEL, "table": "available_slots", "schema": "public"}
