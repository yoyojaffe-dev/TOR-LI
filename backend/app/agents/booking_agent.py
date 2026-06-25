"""Booking Agent (SKELETON).

On-demand worker triggered by POST /bookings/confirm. It navigates to the
original barber's booking site with Playwright, fills the customer's name +
phone into the correct fields (field mapping aided by AI), submits, and returns
the outcome.

Foundation phase: returns a stubbed success so the booking flow is wired
end-to-end. The real Playwright automation lands in the post-review phase.
"""

from app.config import get_settings
from app.supabase_client import get_supabase


class BookingAgent:
    """Submits a reservation on the barber's own booking site."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_supabase()

    def submit(self, slot_id: str, customer_name: str, customer_phone: str) -> dict:
        """Submit the booking for ``slot_id``.

        STUB: returns success without touching a real site so the lock/confirm
        flow can be exercised. Replace with Playwright automation post-review.
        """
        # TODO (Playwright phase):
        #   1. look up the slot's barbershop booking_url + slot_time
        #   2. browser.goto(url); use AI to map name/phone -> form fields
        #   3. fill + click submit; verify confirmation
        #   4. return {"success": True, "confirmation": ...}
        return {
            "success": True,
            "stub": True,
            "slot_id": slot_id,
            "message": "Booking Agent stub — real Playwright submission pending review",
        }
