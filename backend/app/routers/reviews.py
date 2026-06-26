"""Barbershop reviews.

A review is tied to a completed booking: a Customer rates the Barber after an
Appointment. Submission validates the booking belongs to the caller (via the
``submit_review`` RPC); listing exposes masked display names only.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import Review, ReviewRequest
from app.services import locking

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("")
def create_review(req: ReviewRequest) -> dict[str, Any]:
    """Submit (or update) a review for the caller's completed booking."""
    result = locking.submit_review(req.booking_id, req.user_token, req.rating, req.comment)
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"] or "cannot save review")
    return result


@router.get("", response_model=list[Review])
def list_reviews(
    barbershop_id: str = Query(..., description="Barbershop to list reviews for."),
) -> list[Review]:
    """Return recent reviews for a barbershop, newest first."""
    return [Review(**row) for row in locking.list_reviews(barbershop_id)]
