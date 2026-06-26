"""Integration tests against a RUNNING backend (real Supabase RPCs).

These exercise the actual security boundary of submit_review — that a review can
only be written for a booking owned by the caller — which pure unit tests cannot
cover because the ownership check lives in the SECURITY DEFINER SQL function.

Skipped automatically when the backend at localhost:8000 is not reachable, so the
default `pytest` run is unaffected.
"""

import uuid

import httpx
import pytest

BACKEND = "http://localhost:8000"


def _backend_up() -> bool:
    try:
        return httpx.get(f"{BACKEND}/health", timeout=1.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _backend_up(), reason="backend not running on :8000")


def test_review_rejected_for_nonexistent_booking() -> None:
    """A random booking id is not owned by anyone → 409, no row written."""
    res = httpx.post(f"{BACKEND}/reviews", json={
        "booking_id": str(uuid.uuid4()),
        "user_token": f"intg-{uuid.uuid4()}",
        "rating": 5,
        "comment": "should be rejected",
    }, timeout=10.0)
    assert res.status_code == 409
    assert "not found" in res.json()["detail"].lower()


def test_review_rejected_for_another_users_booking() -> None:
    """Security: a user cannot review a booking that belongs to someone else.

    Finds a real booking owned by the E2E token, then tries to review it as a
    different token — the ownership guard in submit_review must reject it (409).
    """
    e2e_token = "e2e-fixed-token-0001"
    bookings = httpx.get(f"{BACKEND}/bookings", params={"user_token": e2e_token}, timeout=10.0).json()
    if not bookings:
        pytest.skip("no E2E booking present to attempt cross-user review")

    victim_booking = bookings[0]["booking_id"]
    attacker = f"attacker-{uuid.uuid4()}"
    res = httpx.post(f"{BACKEND}/reviews", json={
        "booking_id": victim_booking,
        "user_token": attacker,
        "rating": 1,
        "comment": "malicious review attempt",
    }, timeout=10.0)
    assert res.status_code == 409, "ownership guard must block reviewing another user's booking"


def test_nearby_slots_live_shape() -> None:
    """/slots/nearby returns the documented shape (or empty) against the real DB."""
    res = httpx.get(f"{BACKEND}/slots/nearby", params={
        "lat": 32.0853, "lng": 34.7818, "radius": 5000, "limit": 3,
    }, timeout=10.0)
    assert res.status_code == 200
    rows = res.json()
    assert isinstance(rows, list)
    if rows:
        r = rows[0]
        for key in ("slot_id", "slot_time", "service_name", "barbershop_id", "shop_name"):
            assert key in r
