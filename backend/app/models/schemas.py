"""Pydantic v2 request/response models.

These mirror the Supabase tables (``barbershops``, ``available_slots``,
``bookings``) and the PostGIS / locking RPC contracts.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SlotStatus(str, Enum):
    free = "free"
    locked = "locked"
    booked = "booked"


class Barbershop(BaseModel):
    id: str
    name: str
    address: str | None = None
    phone: str | None = None
    booking_url: str | None = None
    google_place_id: str | None = None
    lat: float | None = None
    lng: float | None = None
    opening_hours: dict | None = None
    distance_m: float | None = Field(
        default=None, description="Distance from query point in metres (radius search only)."
    )


class Slot(BaseModel):
    id: str
    barbershop_id: str
    service_name: str
    price: float | None = None
    slot_time: datetime
    status: SlotStatus = SlotStatus.free
    locked_until: datetime | None = None


class LockRequest(BaseModel):
    slot_id: str
    user_token: str = Field(description="Opaque client identifier holding the lock.")


class LockResponse(BaseModel):
    success: bool
    slot_id: str
    locked_until: datetime | None = None
    message: str | None = None


class BookingRequest(BaseModel):
    slot_id: str
    user_token: str
    customer_name: str
    customer_phone: str


class BookingResponse(BaseModel):
    success: bool
    booking_id: str | None = None
    status: str
    message: str | None = None
