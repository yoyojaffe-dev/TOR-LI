"""Pessimistic slot locking.

Locks are enforced in Postgres, not in the app, so concurrent bookers cannot
race. All operations delegate to atomic SQL RPCs defined in the init migration
(``lock_slot`` / ``release_slot`` / ``confirm_booking``).
"""

from typing import Any

from app.config import get_settings
from app.models.schemas import BookingResponse, LockResponse
from app.supabase_client import Row, all_rows, get_supabase, one_row


def acquire_lock(slot_id: str, user_token: str) -> LockResponse:
    """Attempt to lock a free (or expired-lock) slot for ``user_token``.

    Calls the ``lock_slot`` RPC which atomically flips ``status`` to ``locked``
    and sets ``locked_until = now() + ttl`` only when the slot is currently
    bookable. Returns success=False if another user already holds the lock.
    """
    ttl = get_settings().slot_lock_ttl_seconds
    res = (
        get_supabase()
        .rpc(
            "lock_slot",
            {"p_slot_id": slot_id, "p_user": user_token, "p_ttl_seconds": ttl},
        )
        .execute()
    )

    row: Row = one_row(res.data)
    return LockResponse(
        success=bool(row.get("success")),
        slot_id=slot_id,
        locked_until=row.get("locked_until"),
        message=row.get("message"),
    )


def release_lock(slot_id: str, user_token: str) -> LockResponse:
    """Release a lock previously held by ``user_token`` (e.g. user cancelled)."""
    res = get_supabase().rpc("release_slot", {"p_slot_id": slot_id, "p_user": user_token}).execute()
    row: Row = one_row(res.data)
    return LockResponse(
        success=bool(row.get("success")),
        slot_id=slot_id,
        message=row.get("message"),
    )


def confirm_booking(
    slot_id: str,
    user_token: str,
    booking_id: str,
    customer_name: str | None = None,
    customer_phone: str | None = None,
) -> BookingResponse:
    """Finalize a locked slot into a confirmed booking (status -> booked).

    Only succeeds if ``user_token`` still holds a non-expired lock. The RPC also
    inserts the bookings row (with customer details) so it shows in history.
    """
    res = (
        get_supabase()
        .rpc(
            "confirm_booking",
            {
                "p_slot_id": slot_id,
                "p_user": user_token,
                "p_booking_id": booking_id,
                "p_customer_name": customer_name,
                "p_customer_phone": customer_phone,
            },
        )
        .execute()
    )
    row: Row = one_row(res.data)
    return BookingResponse(
        success=bool(row.get("success")),
        booking_id=booking_id,
        status=row.get("status", "unknown"),
        message=row.get("message"),
    )


def list_bookings(user_token: str) -> list[Row]:
    """Return a user's bookings (joined with slot + shop detail) for history."""
    res = get_supabase().rpc("bookings_for_user", {"p_user": user_token}).execute()
    return all_rows(res.data)


def cancel_booking(booking_id: str, user_token: str) -> dict[str, Any]:
    """Cancel a user's booking and free the slot. Returns {success, message}."""
    res = (
        get_supabase()
        .rpc("cancel_booking", {"p_booking_id": booking_id, "p_user": user_token})
        .execute()
    )
    row: Row = one_row(res.data)
    return {"success": bool(row.get("success")), "message": row.get("message")}


def submit_review(
    booking_id: str, user_token: str, rating: int, comment: str | None = None
) -> dict[str, Any]:
    """Submit (or update) a review for a completed booking. Returns {success, message}."""
    res = (
        get_supabase()
        .rpc(
            "submit_review",
            {
                "p_booking_id": booking_id,
                "p_user": user_token,
                "p_rating": rating,
                "p_comment": comment,
            },
        )
        .execute()
    )
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
