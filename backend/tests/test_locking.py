"""Unit tests for pessimistic slot locking (Supabase RPC mocked out)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services import locking


def _mock_supabase(row):
    """Return a fake supabase client whose rpc().execute() yields `row`."""
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=[row])
    return client


def test_acquire_lock_success() -> None:
    client = _mock_supabase(
        {"success": True, "locked_until": "2026-06-25T12:00:00Z", "message": None}
    )
    with patch.object(locking, "get_supabase", return_value=client):
        res = locking.acquire_lock("slot-1", "user-A")
    assert res.success is True
    assert res.slot_id == "slot-1"
    # Pydantic coerces the ISO string to a datetime on the LockResponse model.
    assert res.locked_until == datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    # Correct RPC + args.
    name, args = client.rpc.call_args[0]
    assert name == "lock_slot"
    assert args["p_slot_id"] == "slot-1"
    assert args["p_user"] == "user-A"
    assert "p_ttl_seconds" in args


def test_acquire_lock_rejected_when_already_held() -> None:
    client = _mock_supabase({"success": False, "message": "already locked"})
    with patch.object(locking, "get_supabase", return_value=client):
        res = locking.acquire_lock("slot-1", "user-B")
    assert res.success is False
    assert res.message == "already locked"


def test_acquire_lock_handles_dict_data_not_list() -> None:
    # Some PostgREST responses return a bare object, not a list.
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data={"success": True, "locked_until": "2026-06-25T12:00:00Z"}
    )
    with patch.object(locking, "get_supabase", return_value=client):
        res = locking.acquire_lock("slot-1", "user-A")
    assert res.success is True


def test_acquire_lock_handles_empty_data() -> None:
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=[])
    with patch.object(locking, "get_supabase", return_value=client):
        res = locking.acquire_lock("slot-1", "user-A")
    assert res.success is False


def test_release_lock_success() -> None:
    client = _mock_supabase({"success": True, "message": "released"})
    with patch.object(locking, "get_supabase", return_value=client):
        res = locking.release_lock("slot-1", "user-A")
    assert res.success is True
    assert client.rpc.call_args[0][0] == "release_slot"


def test_confirm_booking_passes_status_through() -> None:
    client = _mock_supabase({"success": True, "status": "booked", "message": None})
    with patch.object(locking, "get_supabase", return_value=client):
        res = locking.confirm_booking("slot-1", "user-A", "booking-9")
    assert res.success is True
    assert res.status == "booked"
    assert res.booking_id == "booking-9"
    name, args = client.rpc.call_args[0]
    assert name == "confirm_booking"
    assert args["p_booking_id"] == "booking-9"


def test_confirm_booking_failure_defaults_status_unknown() -> None:
    client = _mock_supabase({"success": False})
    with patch.object(locking, "get_supabase", return_value=client):
        res = locking.confirm_booking("slot-1", "user-A", "booking-9")
    assert res.success is False
    assert res.status == "unknown"


def test_confirm_booking_passes_customer_details_to_rpc() -> None:
    client = _mock_supabase({"success": True, "status": "booked"})
    with patch.object(locking, "get_supabase", return_value=client):
        locking.confirm_booking("slot-1", "user-A", "bk1", "Dana", "+972500000000")
    args = client.rpc.call_args[0][1]
    assert args["p_customer_name"] == "Dana"
    assert args["p_customer_phone"] == "+972500000000"


def test_list_bookings_returns_rows() -> None:
    rows = [{"booking_id": "bk1", "shop_name": "Cuts", "service_name": "Fade"}]
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=rows)
    with patch.object(locking, "get_supabase", return_value=client):
        out = locking.list_bookings("user-A")
    assert out == rows
    name, args = client.rpc.call_args[0]
    assert name == "bookings_for_user"
    assert args["p_user"] == "user-A"


def test_list_bookings_empty() -> None:
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=None)
    with patch.object(locking, "get_supabase", return_value=client):
        assert locking.list_bookings("user-A") == []


def test_cancel_booking_success() -> None:
    client = _mock_supabase({"success": True, "message": "cancelled"})
    with patch.object(locking, "get_supabase", return_value=client):
        out = locking.cancel_booking("bk1", "user-A")
    assert out["success"] is True
    name, args = client.rpc.call_args[0]
    assert name == "cancel_booking"
    assert args["p_booking_id"] == "bk1"
    assert args["p_user"] == "user-A"


def test_cancel_booking_failure() -> None:
    client = _mock_supabase({"success": False, "message": "not found"})
    with patch.object(locking, "get_supabase", return_value=client):
        out = locking.cancel_booking("bk1", "user-A")
    assert out["success"] is False
    assert out["message"] == "not found"
