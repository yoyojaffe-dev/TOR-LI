"""Pessimistic slot locking.

Locks are enforced in Postgres, not in the app, so concurrent bookers cannot
race. All operations delegate to atomic SQL RPCs defined in the init migration
(``lock_slot`` / ``release_slot`` / ``confirm_booking``).
"""

from app.config import get_settings
from app.models.schemas import BookingResponse, LockResponse
from app.supabase_client import get_supabase


def acquire_lock(slot_id: str, user_token: str) -> LockResponse:
    """Attempt to lock a free (or expired-lock) slot for ``user_token``.

    Calls the ``lock_slot`` RPC which atomically flips ``status`` to ``locked``
    and sets ``locked_until = now() + ttl`` only when the slot is currently
    bookable. Returns success=False if another user already holds the lock.
    """
    ttl = get_settings().slot_lock_ttl_seconds
    res = get_supabase().rpc(
        "lock_slot",
        {"p_slot_id": slot_id, "p_user": user_token, "p_ttl_seconds": ttl},
    ).execute()

    row = res.data[0] if isinstance(res.data, list) and res.data else res.data or {}
    return LockResponse(
        success=bool(row.get("success")),
        slot_id=slot_id,
        locked_until=row.get("locked_until"),
        message=row.get("message"),
    )


def release_lock(slot_id: str, user_token: str) -> LockResponse:
    """Release a lock previously held by ``user_token`` (e.g. user cancelled)."""
    res = get_supabase().rpc(
        "release_slot", {"p_slot_id": slot_id, "p_user": user_token}
    ).execute()
    row = res.data[0] if isinstance(res.data, list) and res.data else res.data or {}
    return LockResponse(
        success=bool(row.get("success")),
        slot_id=slot_id,
        message=row.get("message"),
    )


def confirm_booking(slot_id: str, user_token: str, booking_id: str) -> BookingResponse:
    """Finalize a locked slot into a confirmed booking (status -> booked).

    Only succeeds if ``user_token`` still holds a non-expired lock.
    """
    res = get_supabase().rpc(
        "confirm_booking",
        {"p_slot_id": slot_id, "p_user": user_token, "p_booking_id": booking_id},
    ).execute()
    row = res.data[0] if isinstance(res.data, list) and res.data else res.data or {}
    return BookingResponse(
        success=bool(row.get("success")),
        booking_id=booking_id,
        status=row.get("status", "unknown"),
        message=row.get("message"),
    )
