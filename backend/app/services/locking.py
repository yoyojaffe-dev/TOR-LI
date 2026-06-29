"""Pessimistic slot locking.

Locks are enforced in Postgres, not in the app, so concurrent bookers cannot
race. All operations delegate to atomic SQL RPCs defined in the migrations
(``lock_slot`` / ``release_slot`` / ``confirm_booking``).

The user-scoped operations take an already-authenticated Supabase ``client``
(from ``get_authed_supabase``) and carry NO identity argument: the RPCs read
``auth.uid()`` from the caller's JWT. The read-only discovery paths
(``free_slots`` / ``nearby_slots`` / ``active_deals`` / ``list_reviews``) stay on
the anon client.
"""

from typing import Any

from supabase import Client

from app.config import get_settings
from app.models.schemas import BookingResponse, LockResponse
from app.supabase_client import Row, all_rows, get_supabase, one_row


def acquire_lock(client: Client, slot_id: str) -> LockResponse:
    """Attempt to lock a free (or expired-lock) slot for the caller.

    Calls the ``lock_slot`` RPC which atomically flips ``status`` to ``locked``
    and sets ``locked_until = now() + ttl`` only when the slot is currently
    bookable. Returns success=False if another user already holds the lock.
    """
    ttl = get_settings().slot_lock_ttl_seconds
    res = client.rpc("lock_slot", {"p_slot_id": slot_id, "p_ttl_seconds": ttl}).execute()

    row: Row = one_row(res.data)
    return LockResponse(
        success=bool(row.get("success")),
        slot_id=slot_id,
        locked_until=row.get("locked_until"),
        message=row.get("message"),
    )


def release_lock(client: Client, slot_id: str) -> LockResponse:
    """Release a lock previously held by the caller (e.g. user cancelled)."""
    res = client.rpc("release_slot", {"p_slot_id": slot_id}).execute()
    row: Row = one_row(res.data)
    return LockResponse(
        success=bool(row.get("success")),
        slot_id=slot_id,
        message=row.get("message"),
    )


def confirm_booking(
    client: Client,
    slot_id: str,
    booking_id: str,
    customer_name: str | None = None,
    customer_phone: str | None = None,
) -> BookingResponse:
    """Finalize a locked slot into a confirmed booking (status -> booked).

    Only succeeds if the caller still holds a non-expired lock. The RPC also
    inserts the bookings row (with customer details) so it shows in history.
    """
    res = client.rpc(
        "confirm_booking",
        {
            "p_slot_id": slot_id,
            "p_booking_id": booking_id,
            "p_customer_name": customer_name,
            "p_customer_phone": customer_phone,
        },
    ).execute()
    row: Row = one_row(res.data)
    return BookingResponse(
        success=bool(row.get("success")),
        booking_id=booking_id,
        status=row.get("status", "unknown"),
        message=row.get("message"),
    )


def list_bookings(client: Client) -> list[Row]:
    """Return the caller's bookings (joined with slot + shop detail) for history."""
    res = client.rpc("bookings_for_user", {}).execute()
    return all_rows(res.data)


def cancel_booking(client: Client, booking_id: str) -> dict[str, Any]:
    """Cancel the caller's booking and free the slot. Returns {success, message}."""
    res = client.rpc("cancel_booking", {"p_booking_id": booking_id}).execute()
    row: Row = one_row(res.data)
    return {"success": bool(row.get("success")), "message": row.get("message")}


def submit_review(
    client: Client, booking_id: str, rating: int, comment: str | None = None
) -> dict[str, Any]:
    """Submit (or update) a review for the caller's booking. Returns {success, message}."""
    res = client.rpc(
        "submit_review",
        {"p_booking_id": booking_id, "p_rating": rating, "p_comment": comment},
    ).execute()
    row: Row = one_row(res.data)
    return {"success": bool(row.get("success")), "message": row.get("message")}


def list_reviews(barbershop_id: str) -> list[Row]:
    """Return recent reviews for a barbershop (most recent first)."""
    res = get_supabase().rpc("reviews_for_barbershop", {"p_shop": barbershop_id}).execute()
    return all_rows(res.data)


def free_slots(barbershop_id: str) -> list[Row]:
    """Free, upcoming, non-blocked slots for a shop (respects availability overrides)."""
    res = get_supabase().rpc("free_slots", {"p_barbershop_id": barbershop_id}).execute()
    return all_rows(res.data)


def nearby_slots(lat: float, lng: float, radius_m: int = 5000, lim: int = 20) -> list[Row]:
    """Return free upcoming slots near a point, joined to shop info."""
    res = (
        get_supabase()
        .rpc(
            "available_slots_nearby",
            {
                "lat": lat,
                "lng": lng,
                "radius_m": radius_m,
                "lim": lim,
            },
        )
        .execute()
    )
    return all_rows(res.data)


def active_deals(lat: float, lng: float) -> list[Row]:
    """All currently-bookable deals (is_deal, free, unblocked, active staff+service),
    nearest-first — NOT distance-capped, so deals surface regardless of range."""
    res = get_supabase().rpc("active_deals", {"p_lat": lat, "p_lng": lng}).execute()
    return all_rows(res.data)
