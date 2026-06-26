"""Unit tests for the Booking Agent stub (no real Playwright run)."""

from types import SimpleNamespace

from app.agents.booking_agent import BookingAgent


def _agent() -> BookingAgent:
    agent = BookingAgent.__new__(BookingAgent)  # skip __init__ (no real clients)
    agent.settings = SimpleNamespace()
    agent.db = SimpleNamespace()
    return agent


def test_submit_returns_stub_success_with_slot_id() -> None:
    result = _agent().submit(slot_id="slot-1", customer_name="Dana", customer_phone="+972500000000")
    assert result["success"] is True
    assert result["stub"] is True
    assert result["slot_id"] == "slot-1"
    assert "message" in result
