"""Endpoint tests for the API routers.

The app is exercised through FastAPI's TestClient; the Supabase client, locking
service, and agents are mocked so no network/DB calls happen. TestClient is used
without a `with` block so the lifespan (APScheduler) does not start.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _supabase_returning(data):
    """Fake supabase client whose any fluent chain ends in .execute().data == data."""
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = SimpleNamespace(data=data)
    # Cover the .table().select()...execute() chain too (all return the same mock).
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=data
    )
    chain = sb.table.return_value.select.return_value.eq.return_value
    chain.order.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=data)
    chain.order.return_value.execute.return_value = SimpleNamespace(data=data)
    return sb


# ── /barbershops ─────────────────────────────────────────────────────────────


def test_list_barbershops_returns_rows() -> None:
    rows = [{"id": "b1", "name": "Cuts", "distance_m": 42.0}]
    with patch("app.routers.barbershops.get_supabase", return_value=_supabase_returning(rows)):
        res = client.get("/barbershops", params={"lat": 32.0, "lng": 34.7, "radius": 2000})
    assert res.status_code == 200
    body = res.json()
    assert body[0]["id"] == "b1"
    assert body[0]["distance_m"] == 42.0


def test_list_barbershops_empty() -> None:
    with patch("app.routers.barbershops.get_supabase", return_value=_supabase_returning([])):
        res = client.get("/barbershops", params={"lat": 32.0, "lng": 34.7})
    assert res.status_code == 200
    assert res.json() == []


def test_list_barbershops_requires_lat_lng() -> None:
    res = client.get("/barbershops")  # missing required lat/lng
    assert res.status_code == 422


def test_list_barbershops_rejects_out_of_range_radius() -> None:
    res = client.get("/barbershops", params={"lat": 32, "lng": 34, "radius": 999999})
    assert res.status_code == 422


def test_list_barbershops_db_error_becomes_502() -> None:
    sb = MagicMock()
    sb.rpc.return_value.execute.side_effect = Exception("pg down")
    with patch("app.routers.barbershops.get_supabase", return_value=sb):
        res = client.get("/barbershops", params={"lat": 32.0, "lng": 34.7})
    assert res.status_code == 502


def test_get_barbershop_404_when_missing() -> None:
    with patch("app.routers.barbershops.get_supabase", return_value=_supabase_returning([])):
        res = client.get("/barbershops/nope")
    assert res.status_code == 404


# ── /slots ───────────────────────────────────────────────────────────────────


def test_list_slots_returns_rows() -> None:
    rows = [
        {
            "id": "s1",
            "barbershop_id": "b1",
            "service_name": "Cut",
            "price": 80,
            "slot_time": "2026-06-26T09:00:00+03:00",
            "status": "free",
        }
    ]
    with patch("app.routers.slots.get_supabase", return_value=_supabase_returning(rows)):
        res = client.get("/slots", params={"barbershop_id": "b1"})
    assert res.status_code == 200
    assert res.json()[0]["service_name"] == "Cut"


def test_list_slots_requires_barbershop_id() -> None:
    assert client.get("/slots").status_code == 422


def test_realtime_info_shape() -> None:
    body = client.get("/slots/realtime-info").json()
    assert body["table"] == "available_slots"
    assert body["schema"] == "public"
    assert "channel" in body


# ── /bookings ────────────────────────────────────────────────────────────────


def test_lock_success() -> None:
    from app.models.schemas import LockResponse

    ok = LockResponse(success=True, slot_id="s1", locked_until=None, message=None)
    with patch("app.routers.bookings.locking.acquire_lock", return_value=ok):
        res = client.post("/bookings/lock", json={"slot_id": "s1", "user_token": "u1"})
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_lock_conflict_returns_409() -> None:
    from app.models.schemas import LockResponse

    taken = LockResponse(success=False, slot_id="s1", message="already locked")
    with patch("app.routers.bookings.locking.acquire_lock", return_value=taken):
        res = client.post("/bookings/lock", json={"slot_id": "s1", "user_token": "u2"})
    assert res.status_code == 409
    assert res.json()["detail"] == "already locked"


def test_confirm_success_path() -> None:
    from app.models.schemas import BookingResponse

    confirmed = BookingResponse(success=True, booking_id="bk1", status="booked")
    with (
        patch("app.routers.bookings.BookingAgent") as Agent,
        patch("app.routers.bookings.locking.confirm_booking", return_value=confirmed) as conf,
    ):
        Agent.return_value.submit.return_value = {"success": True, "stub": True}
        res = client.post(
            "/bookings/confirm",
            json={
                "slot_id": "s1",
                "user_token": "u1",
                "customer_name": "Dana",
                "customer_phone": "+972500000000",
            },
        )
    assert res.status_code == 201  # booking resource created
    assert res.json()["status"] == "booked"
    conf.assert_called_once()


def test_confirm_releases_lock_and_502_when_agent_fails() -> None:
    with (
        patch("app.routers.bookings.BookingAgent") as Agent,
        patch("app.routers.bookings.locking.release_lock") as release,
    ):
        Agent.return_value.submit.return_value = {"success": False}
        res = client.post(
            "/bookings/confirm",
            json={
                "slot_id": "s1",
                "user_token": "u1",
                "customer_name": "Dana",
                "customer_phone": "+972500000000",
            },
        )
    assert res.status_code == 502
    release.assert_called_once()  # lock released on agent failure


def test_confirm_validation_error_missing_fields() -> None:
    res = client.post("/bookings/confirm", json={"slot_id": "s1", "user_token": "u1"})
    assert res.status_code == 422


def test_confirm_forwards_customer_details() -> None:
    from app.models.schemas import BookingResponse

    confirmed = BookingResponse(success=True, booking_id="bk1", status="booked")
    with (
        patch("app.routers.bookings.BookingAgent") as Agent,
        patch("app.routers.bookings.locking.confirm_booking", return_value=confirmed) as conf,
    ):
        Agent.return_value.submit.return_value = {"success": True}
        client.post(
            "/bookings/confirm",
            json={
                "slot_id": "s1",
                "user_token": "u1",
                "customer_name": "Dana",
                "customer_phone": "+972500000000",
            },
        )
    # name/phone forwarded to the service as kwargs.
    assert conf.call_args.kwargs["customer_name"] == "Dana"
    assert conf.call_args.kwargs["customer_phone"] == "+972500000000"


def test_list_bookings_endpoint() -> None:
    # Mirrors the bookings_for_user RPC shape (status is always present).
    rows = [
        {
            "booking_id": "bk1",
            "status": "confirmed",
            "shop_name": "Cuts",
            "service_name": "Fade",
            "price": 120,
            "slot_time": "2026-06-26T09:00:00+03:00",
            "barbershop_id": "b1",
            "shop_address": "Main St",
        }
    ]
    with patch("app.routers.bookings.locking.list_bookings", return_value=rows) as lb:
        res = client.get("/bookings", params={"user_token": "u1"})
    assert res.status_code == 200
    assert res.json()[0]["shop_name"] == "Cuts"
    assert res.json()[0]["status"] == "confirmed"
    assert lb.call_args[0][0] == "u1"


def test_list_bookings_response_is_filtered_to_history_schema() -> None:
    # response_model strips fields not on BookingHistoryItem (e.g. user_token).
    rows = [
        {
            "booking_id": "bk1",
            "status": "confirmed",
            "shop_name": "Cuts",
            "service_name": "Fade",
            "user_token": "secret-token",  # must NOT leak through response_model
        }
    ]
    with patch("app.routers.bookings.locking.list_bookings", return_value=rows):
        res = client.get("/bookings", params={"user_token": "u1"})
    assert res.status_code == 200
    assert "user_token" not in res.json()[0]


def test_list_bookings_requires_user_token() -> None:
    assert client.get("/bookings").status_code == 422


def test_cancel_booking_ok() -> None:
    with patch(
        "app.routers.bookings.locking.cancel_booking",
        return_value={"success": True, "message": "cancelled"},
    ) as cb:
        res = client.post("/bookings/cancel", json={"booking_id": "bk1", "user_token": "u1"})
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert cb.call_args[0] == ("bk1", "u1")


def test_cancel_booking_conflict() -> None:
    with patch(
        "app.routers.bookings.locking.cancel_booking",
        return_value={"success": False, "message": "not found"},
    ):
        res = client.post("/bookings/cancel", json={"booking_id": "bk1", "user_token": "u1"})
    assert res.status_code == 409


def test_cancel_booking_validation() -> None:
    assert client.post("/bookings/cancel", json={"booking_id": "bk1"}).status_code == 422


# ── /admin ───────────────────────────────────────────────────────────────────


def test_admin_discovery_run() -> None:
    with patch("app.routers.admin.DiscoveryAgent") as Agent:
        Agent.return_value.discover.return_value = 7
        res = client.post(
            "/admin/discovery/run", params={"lat": 32.0, "lng": 34.7, "radius_m": 3000}
        )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["barbershops_upserted"] == 7


def test_admin_discovery_error_becomes_502() -> None:
    with patch("app.routers.admin.DiscoveryAgent") as Agent:
        Agent.return_value.discover.side_effect = Exception("maps down")
        res = client.post("/admin/discovery/run", params={"lat": 32.0, "lng": 34.7})
    assert res.status_code == 502


def test_admin_scraping_run() -> None:
    async def fake_run_once():
        return {"shops_processed": 3, "slots_written": 12}

    with patch("app.routers.admin.ScrapingAgent") as Agent:
        Agent.return_value.run_once = fake_run_once
        res = client.post("/admin/scraping/run")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["slots_written"] == 12


def test_admin_scraping_error_becomes_502() -> None:
    async def boom():
        raise Exception("playwright down")

    with patch("app.routers.admin.ScrapingAgent") as Agent:
        Agent.return_value.run_once = boom
        res = client.post("/admin/scraping/run")
    assert res.status_code == 502


# ── Input validation (Pydantic V2 request hardening) ─────────────────────────


def test_confirm_rejects_blank_customer_name() -> None:
    res = client.post(
        "/bookings/confirm",
        json={
            "slot_id": "s1",
            "user_token": "u1",
            "customer_name": "   ",  # whitespace -> stripped to "" -> min_length fails
            "customer_phone": "+972500000000",
        },
    )
    assert res.status_code == 422


def test_confirm_rejects_phone_without_enough_digits() -> None:
    res = client.post(
        "/bookings/confirm",
        json={
            "slot_id": "s1",
            "user_token": "u1",
            "customer_name": "Dana",
            "customer_phone": "+++----",  # no digits
        },
    )
    assert res.status_code == 422


def test_confirm_strips_whitespace_on_customer_name() -> None:
    from app.models.schemas import BookingResponse

    confirmed = BookingResponse(success=True, booking_id="bk1", status="booked")
    with (
        patch("app.routers.bookings.BookingAgent") as Agent,
        patch("app.routers.bookings.locking.confirm_booking", return_value=confirmed) as conf,
    ):
        Agent.return_value.submit.return_value = {"success": True}
        client.post(
            "/bookings/confirm",
            json={
                "slot_id": "s1",
                "user_token": "u1",
                "customer_name": "  Dana  ",
                "customer_phone": "  +972 50 000 0000 ",
            },
        )
    # str_strip_whitespace trims before the value reaches the service layer.
    assert conf.call_args.kwargs["customer_name"] == "Dana"


def test_lock_rejects_blank_slot_id() -> None:
    res = client.post("/bookings/lock", json={"slot_id": "", "user_token": "u1"})
    assert res.status_code == 422


def test_review_rejects_blank_user_token() -> None:
    res = client.post(
        "/reviews",
        json={"booking_id": "bk1", "user_token": "  ", "rating": 5},
    )
    assert res.status_code == 422


def test_review_rejects_overlong_comment() -> None:
    res = client.post(
        "/reviews",
        json={"booking_id": "bk1", "user_token": "u1", "rating": 5, "comment": "x" * 1001},
    )
    assert res.status_code == 422
