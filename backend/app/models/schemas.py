"""Pydantic v2 request/response models.

These mirror the Supabase tables (``barbershops``, ``available_slots``,
``bookings``) and the PostGIS / locking RPC contracts.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _RequestModel(BaseModel):
    """Base for inbound payloads: trims surrounding whitespace on all strings.

    With ``str_strip_whitespace`` a whitespace-only value collapses to "" and
    then fails the ``min_length=1`` constraints below, so blank identifiers /
    customer details are rejected with HTTP 422 instead of reaching the DB.
    """

    model_config = ConfigDict(str_strip_whitespace=True)


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
    opening_hours: dict[str, Any] | None = None
    photo_url: str | None = None
    photo_urls: list[str] = []
    rating: float | None = None
    rating_count: int | None = None
    place_type: str | None = None
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


class LockRequest(_RequestModel):
    slot_id: str = Field(min_length=1)
    user_token: str = Field(min_length=1, description="Opaque client identifier holding the lock.")


class LockResponse(BaseModel):
    success: bool
    slot_id: str
    locked_until: datetime | None = None
    message: str | None = None


class BookingRequest(_RequestModel):
    slot_id: str = Field(min_length=1)
    user_token: str = Field(min_length=1)
    customer_name: str = Field(min_length=1, max_length=80)
    customer_phone: str = Field(min_length=7, max_length=20)

    @field_validator("customer_phone")
    @classmethod
    def _phone_has_enough_digits(cls, v: str) -> str:
        """Require at least 7 digits so a punctuation-only phone is rejected."""
        if sum(c.isdigit() for c in v) < 7:
            raise ValueError("phone must contain at least 7 digits")
        return v


class CancelRequest(_RequestModel):
    booking_id: str = Field(min_length=1)
    user_token: str = Field(min_length=1)


class BookingResponse(BaseModel):
    success: bool
    booking_id: str | None = None
    status: str
    message: str | None = None


class ReviewRequest(_RequestModel):
    booking_id: str = Field(min_length=1)
    user_token: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class Review(BaseModel):
    id: str
    rating: int
    comment: str | None = None
    created_at: str | None = None
    display_name: str | None = None


class ActionResult(BaseModel):
    """Generic success/message envelope for state-changing RPC endpoints."""

    success: bool
    message: str | None = None


class BookingHistoryItem(BaseModel):
    """A row from the ``bookings_for_user`` RPC (booking joined to slot + shop)."""

    booking_id: str
    status: str
    created_at: str | None = None
    service_name: str | None = None
    price: float | None = None
    slot_time: str | None = None
    barbershop_id: str | None = None
    shop_name: str | None = None
    shop_address: str | None = None


class NearbySlot(BaseModel):
    slot_id: str
    slot_time: str
    service_name: str
    price: float | None = None
    barbershop_id: str
    shop_name: str
    shop_address: str | None = None
    lat_out: float | None = None
    lng_out: float | None = None
    distance_m: float | None = None
