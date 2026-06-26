"""Booking flow: lock -> confirm.

A booking links a customer to a barbershop + slot at a time. The flow is:
1. POST /bookings/lock   -> pessimistic lock held while the user authorizes payment
2. POST /bookings/confirm -> Booking Agent submits on the barber's site, slot -> booked

The Playwright submission in step 2 is stubbed for now (foundation phase).
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.agents.booking_agent import BookingAgent
from app.models.schemas import (
    BookingRequest,
    BookingResponse,
    CancelRequest,
    LockRequest,
    LockResponse,
)
from app.services import locking
from app.supabase_client import Row

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("")
def list_bookings(
    user_token: str = Query(..., description="Browser token that holds the bookings."),
) -> list[Row]:
    """Return the caller's bookings (slot + shop detail), newest slot first."""
    return locking.list_bookings(user_token)


@router.post("/cancel")
def cancel_booking(req: CancelRequest) -> dict[str, Any]:
    """Cancel the caller's booking and free the slot."""
    result = locking.cancel_booking(req.booking_id, req.user_token)
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"] or "cannot cancel")
    return result


@router.post("/lock", response_model=LockResponse)
def lock_slot(req: LockRequest) -> LockResponse:
    """Acquire a short pessimistic lock so no one else can take the slot."""
    result = locking.acquire_lock(req.slot_id, req.user_token)
    if not result.success:
        raise HTTPException(status_code=409, detail=result.message or "slot unavailable")
    return result


@router.post("/release", response_model=LockResponse)
def release_slot(req: LockRequest) -> LockResponse:
    """Manually release a held lock (user backed out)."""
    return locking.release_lock(req.slot_id, req.user_token)


@router.post("/confirm", response_model=BookingResponse)
def confirm_booking(req: BookingRequest) -> BookingResponse:
    """Confirm a locked slot: run the Booking Agent, then mark it booked."""
    booking_id = str(uuid.uuid4())

    # On-demand Booking Agent submits the reservation on the barber's site.
    # SKELETON: returns a stubbed success until the Playwright phase lands.
    agent_result = BookingAgent().submit(
        slot_id=req.slot_id,
        customer_name=req.customer_name,
        customer_phone=req.customer_phone,
    )
    if not agent_result.get("success"):
        locking.release_lock(req.slot_id, req.user_token)
        raise HTTPException(status_code=502, detail="booking submission failed")

    return locking.confirm_booking(
        req.slot_id,
        req.user_token,
        booking_id,
        customer_name=req.customer_name,
        customer_phone=req.customer_phone,
    )
