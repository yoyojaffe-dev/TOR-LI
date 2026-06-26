"""Tests for reviews endpoints + /slots/nearby and their locking wrappers.

Mirrors test_routers.py (TestClient + mocked locking) and test_locking.py
(mocked get_supabase). No network/DB calls happen.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import locking

client = TestClient(app)


def _mock_supabase(data):
    """Return a fake supabase client whose rpc().execute().data == data."""
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = SimpleNamespace(data=data)
    return sb


# ── POST /reviews ─────────────────────────────────────────────────────────────

def test_create_review_success() -> None:
    with patch("app.routers.reviews.locking.submit_review",
               return_value={"success": True, "message": "saved"}) as sr:
        res = client.post("/reviews", json={
            "booking_id": "bk1", "user_token": "u1", "rating": 5, "comment": "great",
        })
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert sr.call_args[0] == ("bk1", "u1", 5, "great")


def test_create_review_conflict_returns_409() -> None:
    with patch("app.routers.reviews.locking.submit_review",
               return_value={"success": False, "message": "booking not found for this user"}):
        res = client.post("/reviews", json={
            "booking_id": "bk1", "user_token": "u1", "rating": 4,
        })
    assert res.status_code == 409
    assert res.json()["detail"] == "booking not found for this user"


def test_create_review_validation_missing_fields() -> None:
    res = client.post("/reviews", json={"booking_id": "bk1", "user_token": "u1"})
    assert res.status_code == 422


def test_create_review_validation_rating_out_of_range() -> None:
    res = client.post("/reviews", json={
        "booking_id": "bk1", "user_token": "u1", "rating": 9,
    })
    assert res.status_code == 422


import pytest


@pytest.mark.parametrize("rating,expected", [
    (0, 422),   # below min (Field ge=1)
    (1, 200),   # lower bound, valid
    (5, 200),   # upper bound, valid
    (6, 422),   # above max (Field le=5)
    (-3, 422),  # negative
])
def test_create_review_rating_boundaries(rating: int, expected: int) -> None:
    with patch("app.routers.reviews.locking.submit_review",
               return_value={"success": True, "message": "saved"}):
        res = client.post("/reviews", json={
            "booking_id": "bk1", "user_token": "u1", "rating": rating,
        })
    assert res.status_code == expected


def test_create_review_rating_must_be_integer() -> None:
    # A fractional rating is rejected (schema is int).
    res = client.post("/reviews", json={
        "booking_id": "bk1", "user_token": "u1", "rating": 3.5,
    })
    assert res.status_code == 422


# ── GET /reviews ──────────────────────────────────────────────────────────────

def test_list_reviews_returns_rows() -> None:
    rows = [
        {"id": "r1", "rating": 5, "comment": "great", "created_at": "2026-06-25T12:00:00Z",
         "display_name": "D."},
    ]
    with patch("app.routers.reviews.locking.list_reviews", return_value=rows) as lr:
        res = client.get("/reviews", params={"barbershop_id": "b1"})
    assert res.status_code == 200
    body = res.json()
    assert body[0]["id"] == "r1"
    assert body[0]["display_name"] == "D."
    assert lr.call_args[0][0] == "b1"


def test_list_reviews_requires_barbershop_id() -> None:
    assert client.get("/reviews").status_code == 422


# ── GET /slots/nearby ─────────────────────────────────────────────────────────

def test_nearby_slots_returns_rows() -> None:
    rows = [{
        "slot_id": "s1", "slot_time": "2026-06-26T09:00:00+03:00", "service_name": "Cut",
        "price": 80, "barbershop_id": "b1", "shop_name": "Cuts", "shop_address": "Main St",
        "lat_out": 32.0, "lng_out": 34.7, "distance_m": 120.0,
    }]
    with patch("app.routers.slots.locking.nearby_slots", return_value=rows) as ns:
        res = client.get("/slots/nearby", params={"lat": 32.0, "lng": 34.7})
    assert res.status_code == 200
    body = res.json()
    assert body[0]["slot_id"] == "s1"
    assert body[0]["distance_m"] == 120.0
    assert ns.call_args[0][0] == 32.0
    assert ns.call_args[0][1] == 34.7


def test_nearby_slots_requires_lat_lng() -> None:
    assert client.get("/slots/nearby").status_code == 422


def test_nearby_slots_rejects_out_of_range_radius() -> None:
    # radius bounds: ge=1, le=50000
    assert client.get("/slots/nearby", params={"lat": 32, "lng": 34, "radius": 0}).status_code == 422
    assert client.get("/slots/nearby", params={"lat": 32, "lng": 34, "radius": 99999}).status_code == 422


def test_nearby_slots_rejects_out_of_range_limit() -> None:
    # limit bounds: ge=1, le=100
    assert client.get("/slots/nearby", params={"lat": 32, "lng": 34, "limit": 0}).status_code == 422
    assert client.get("/slots/nearby", params={"lat": 32, "lng": 34, "limit": 101}).status_code == 422


def test_nearby_slots_forwards_radius_and_limit() -> None:
    with patch("app.routers.slots.locking.nearby_slots", return_value=[]) as ns:
        res = client.get("/slots/nearby", params={"lat": 32.0, "lng": 34.7, "radius": 3000, "limit": 7})
    assert res.status_code == 200
    # positional call: (lat, lng, radius, limit)
    assert ns.call_args[0] == (32.0, 34.7, 3000, 7)


def test_nearby_slots_invalid_lat_type_422() -> None:
    assert client.get("/slots/nearby", params={"lat": "abc", "lng": 34.7}).status_code == 422


def test_nearby_slots_db_error_becomes_502() -> None:
    with patch("app.routers.slots.locking.nearby_slots", side_effect=Exception("pg down")):
        res = client.get("/slots/nearby", params={"lat": 32.0, "lng": 34.7})
    assert res.status_code == 502


# ── locking service unit tests ────────────────────────────────────────────────

def test_submit_review_success() -> None:
    sb = _mock_supabase([{"success": True, "message": "saved"}])
    with patch.object(locking, "get_supabase", return_value=sb):
        out = locking.submit_review("bk1", "u1", 5, "great")
    assert out["success"] is True
    assert out["message"] == "saved"
    name, args = sb.rpc.call_args[0]
    assert name == "submit_review"
    assert args["p_booking_id"] == "bk1"
    assert args["p_user"] == "u1"
    assert args["p_rating"] == 5
    assert args["p_comment"] == "great"


def test_submit_review_failure() -> None:
    sb = _mock_supabase([{"success": False, "message": "booking not found for this user"}])
    with patch.object(locking, "get_supabase", return_value=sb):
        out = locking.submit_review("bk1", "u1", 5)
    assert out["success"] is False
    assert out["message"] == "booking not found for this user"


def test_list_reviews_returns_rows_unit() -> None:
    rows = [{"id": "r1", "rating": 5, "display_name": "D."}]
    sb = _mock_supabase(rows)
    with patch.object(locking, "get_supabase", return_value=sb):
        out = locking.list_reviews("b1")
    assert out == rows
    name, args = sb.rpc.call_args[0]
    assert name == "reviews_for_barbershop"
    assert args["p_shop"] == "b1"


def test_list_reviews_empty() -> None:
    sb = _mock_supabase(None)
    with patch.object(locking, "get_supabase", return_value=sb):
        assert locking.list_reviews("b1") == []


def test_nearby_slots_unit() -> None:
    rows = [{"slot_id": "s1", "shop_name": "Cuts"}]
    sb = _mock_supabase(rows)
    with patch.object(locking, "get_supabase", return_value=sb):
        out = locking.nearby_slots(32.0, 34.7, 3000, 10)
    assert out == rows
    name, args = sb.rpc.call_args[0]
    assert name == "available_slots_nearby"
    assert args["lat"] == 32.0
    assert args["lng"] == 34.7
    assert args["radius_m"] == 3000
    assert args["lim"] == 10


def test_nearby_slots_empty() -> None:
    sb = _mock_supabase(None)
    with patch.object(locking, "get_supabase", return_value=sb):
        assert locking.nearby_slots(32.0, 34.7) == []
