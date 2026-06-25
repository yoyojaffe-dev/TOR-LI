"""Barbershop discovery + location radius search.

Data flow: Barbers own Services (slots) and Appointments (bookings). This
router is the read entry point — it returns barbershops near the user's GPS
position using the PostGIS ``barbershops_within_radius`` RPC (ST_DWithin over a
GiST-indexed geography column).
"""

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import Barbershop
from app.supabase_client import get_supabase

router = APIRouter(prefix="/barbershops", tags=["barbershops"])


@router.get("", response_model=list[Barbershop])
def list_barbershops(
    lat: float = Query(..., description="User latitude (WGS84)."),
    lng: float = Query(..., description="User longitude (WGS84)."),
    radius: int = Query(2000, ge=1, le=50000, description="Search radius in metres."),
) -> list[Barbershop]:
    """Return barbershops within ``radius`` metres, nearest first."""
    try:
        res = get_supabase().rpc(
            "barbershops_within_radius",
            {"lat": lat, "lng": lng, "radius_m": radius},
        ).execute()
    except Exception as exc:  # surface DB/RPC errors as 502
        raise HTTPException(status_code=502, detail=f"radius query failed: {exc}") from exc

    return [Barbershop(**row) for row in (res.data or [])]


@router.get("/{barbershop_id}", response_model=Barbershop)
def get_barbershop(barbershop_id: str) -> Barbershop:
    """Return a single barbershop by id."""
    res = (
        get_supabase()
        .table("barbershops")
        .select("*")
        .eq("id", barbershop_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="barbershop not found")
    return Barbershop(**res.data[0])
