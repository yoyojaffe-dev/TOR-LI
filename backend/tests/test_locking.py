"""Unit tests for pessimistic slot locking (Supabase RPC mocked out).

The user-scoped operations now take an already-authenticated client and carry no
identity argument — the RPCs read auth.uid() from the caller's JWT. Tests pass a
mock client directly.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services import locking


def _mock_client(row):
    """Return a fake supabase client whose rpc().execute() yields `row`."""
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=[row])
    return client


def test_acquire_lock_success() -> None:
    client = _mock_client(
        {"success": True, "locked_until": "2026-06-25T12:00:00Z", "message": None}
    )
    res = locking.acquire_lock(client, "slot-1")
    assert res.success is True
    assert res.slot_id == "slot-1"
    # Pydantic coerces the ISO string to a datetime on the LockResponse model.
    assert res.locked_until == datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    # Correct RPC + args (no identity arg — auth.uid() supplies it).
    name, args = client.rpc.call_args[0]
    assert name == "lock_slot"
    assert args["p_slot_id"] == "slot-1"
    assert "p_user" not in args
    assert "p_ttl_seconds" in args


def test_acquire_lock_rejected_when_already_held() -> None:
    client = _mock_client({"success": False, "message": "already locked"})
    res = locking.acquire_lock(client, "slot-1")
    assert res.success is False
    assert res.message == "already locked"


def test_acquire_lock_handles_dict_data_not_list() -> None:
    # Some PostgREST responses return a bare object, not a list.
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data={"success": True, "locked_until": "2026-06-25T12:00:00Z"}
    )
    res = locking.acquire_lock(client, "slot-1")
    assert res.success is True


def test_acquire_lock_handles_empty_data() -> None:
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=[])
    res = locking.acquire_lock(client, "slot-1")
    assert res.success is False


def test_release_lock_success() -> None:
    client = _mock_client({"success": True, "message": "released"})
    res = locking.release_lock(client, "slot-1")
    assert res.success is True
    name, args = client.rpc.call_args[0]
    assert name == "release_slot"
    assert args == {"p_slot_id": "slot-1"}


def test_confirm_booking_passes_status_through() -> None:
    client = _mock_client({"success": True, "status": "booked", "message": None})
    res = locking.confirm_booking(client, "slot-1", "booking-9")
    assert res.success is True
    assert res.status == "booked"
    assert res.booking_id == "booking-9"
    name, args = client.rpc.call_args[0]
    assert name == "confirm_booking"
    assert args["p_booking_id"] == "booking-9"
    assert "p_user" not in args


def test_confirm_booking_failure_defaults_status_unknown() -> None:
    client = _mock_client({"success": False})
    res = locking.confirm_booking(client, "slot-1", "booking-9")
    assert res.success is False
    assert res.status == "unknown"


def test_confirm_booking_passes_customer_details_to_rpc() -> None:
    client = _mock_client({"success": True, "status": "booked"})
    locking.confirm_booking(client, "slot-1", "bk1", "Dana", "+972500000000")
    args = client.rpc.call_args[0][1]
    assert args["p_customer_name"] == "Dana"
    assert args["p_customer_phone"] == "+972500000000"


def test_list_bookings_returns_rows() -> None:
    rows = [{"booking_id": "bk1", "shop_name": "Cuts", "service_name": "Fade"}]
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=rows)
    out = locking.list_bookings(client)
    assert out == rows
    name, args = client.rpc.call_args[0]
    assert name == "bookings_for_user"
    assert args == {}


def test_list_bookings_empty() -> None:
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=None)
    assert locking.list_bookings(client) == []


def test_cancel_booking_success() -> None:
    client = _mock_client({"success": True, "message": "cancelled"})
    out = locking.cancel_booking(client, "bk1")
    assert out["success"] is True
    name, args = client.rpc.call_args[0]
    assert name == "cancel_booking"
    assert args == {"p_booking_id": "bk1"}


def test_cancel_booking_failure() -> None:
    client = _mock_client({"success": False, "message": "not found"})
    out = locking.cancel_booking(client, "bk1")
    assert out["success"] is False
    assert out["message"] == "not found"
