"""Booking flow: lock -> confirm.

A booking links a customer to a barbershop + slot at a time. The flow is:
1. POST /bookings/lock   -> pessimistic lock held while the user authorizes payment
2. POST /bookings/confirm -> Booking Agent submits on the barber's site, slot -> booked
"""

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.agents.booking_agent import BookingAgent
from app.dependencies import get_authed_supabase
from app.models.schemas import (
    ActionResult,
    BookingHistoryItem,
    BookingRequest,
    BookingResponse,
    CancelRequest,
    LockRequest,
    LockResponse,
)
from app.services import locking
from app.supabase_client import Row

router = APIRouter(prefix="/bookings", tags=["bookings"])

# Every booking route runs as the authenticated caller; the RPCs scope by auth.uid().
AuthedClient = Annotated[Client, Depends(get_authed_supabase)]


@router.get("", response_model=list[BookingHistoryItem])
def list_bookings(client: AuthedClient) -> list[Row]:
    """Return the caller's bookings (slot + shop detail), newest slot first."""
    return locking.list_bookings(client)


@router.post("/cancel", response_model=ActionResult)
def cancel_booking(req: CancelRequest, client: AuthedClient) -> Row:
    """Cancel the caller's booking and free the slot."""
    result = locking.cancel_booking(client, req.booking_id)
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"] or "cannot cancel")
    return result


@router.post("/lock", response_model=LockResponse)
def lock_slot(req: LockRequest, client: AuthedClient) -> LockResponse:
    """Acquire a short pessimistic lock so no one else can take the slot."""
    result = locking.acquire_lock(client, req.slot_id)
    if not result.success:
        raise HTTPException(status_code=409, detail=result.message or "slot unavailable")
    return result


@router.post("/release", response_model=LockResponse)
def release_slot(req: LockRequest, client: AuthedClient) -> LockResponse:
    """Manually release a held lock (user backed out)."""
    return locking.release_lock(client, req.slot_id)


@router.post("/confirm", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def confirm_booking(req: BookingRequest, client: AuthedClient) -> BookingResponse:
    """Confirm a locked slot: run the Booking Agent, then mark it booked."""
    booking_id = str(uuid.uuid4())

    # On-demand Booking Agent submits the reservation on the barber's site.
    # This is a sync route (threadpool, no running loop) so asyncio.run is safe.
    agent_result = asyncio.run(
        BookingAgent().submit(
            slot_id=req.slot_id,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
        )
    )
    if not agent_result.get("success"):
        # Shops with no external booking site (active in-DB partners / seeded
        # data) are booked directly in our own database — the app IS their
        # booking system. Any other failure is a genuine submission error.
        if agent_result.get("reason") != "no booking_url":
            locking.release_lock(client, req.slot_id)
            raise HTTPException(status_code=502, detail="booking submission failed")

    return locking.confirm_booking(
        client,
        req.slot_id,
        booking_id,
        customer_name=req.customer_name,
        customer_phone=req.customer_phone,
    )
