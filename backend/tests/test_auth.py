"""Tests for the client phone-OTP auth router and the session dependencies.

GoTrue (Supabase Auth) is mocked — ``app.routers.auth.get_supabase`` and
``app.dependencies.get_supabase`` are patched so no network calls happen.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies import CurrentUser, get_authed_supabase, get_current_user
from app.main import app
from app.models.schemas import _to_e164

client = TestClient(app)


class _GotrueError(Exception):
    """Stand-in for gotrue's AuthApiError, which carries an HTTP ``status``."""

    def __init__(self, status: int) -> None:
        super().__init__(f"gotrue {status}")
        self.status = status


# ── /auth/send-otp ───────────────────────────────────────────────────────────


def test_send_otp_success_normalises_phone() -> None:
    sb = MagicMock()
    with patch("app.routers.auth.get_supabase", return_value=sb):
        res = client.post("/auth/send-otp", json={"phone": "050-123-4567"})
    assert res.status_code == 200
    assert res.json()["success"] is True
    # Local Israeli number normalised to E.164 before reaching GoTrue.
    assert sb.auth.sign_in_with_otp.call_args[0][0] == {"phone": "+972501234567"}


def test_send_otp_rate_limited_returns_429() -> None:
    sb = MagicMock()
    sb.auth.sign_in_with_otp.side_effect = _GotrueError(429)
    with patch("app.routers.auth.get_supabase", return_value=sb):
        res = client.post("/auth/send-otp", json={"phone": "0501234567"})
    assert res.status_code == 429


def test_send_otp_provider_unconfigured_returns_503() -> None:
    sb = MagicMock()
    sb.auth.sign_in_with_otp.side_effect = _GotrueError(500)
    with patch("app.routers.auth.get_supabase", return_value=sb):
        res = client.post("/auth/send-otp", json={"phone": "0501234567"})
    assert res.status_code == 503


def test_send_otp_rejects_phone_without_enough_digits() -> None:
    # Passes the length constraint but has no usable digits -> validator 422.
    res = client.post("/auth/send-otp", json={"phone": "+++----"})
    assert res.status_code == 422


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("050-123-4567", "+972501234567"),  # local 0-prefixed
        ("+972 50 123 4567", "+972501234567"),  # already E.164
        ("972501234567", "+972501234567"),  # country code, no plus
        ("501234567", "+501234567"),  # bare digits -> prefixed with +
    ],
)
def test_to_e164_normalisation(raw: str, expected: str) -> None:
    assert _to_e164(raw) == expected


# ── /auth/verify-otp ─────────────────────────────────────────────────────────


def test_verify_otp_success_returns_session() -> None:
    session = SimpleNamespace(
        access_token="acc", refresh_token="ref", expires_at=1_700_000_000, expires_in=3600
    )
    user = SimpleNamespace(id="uid-1")
    sb = MagicMock()
    sb.auth.verify_otp.return_value = SimpleNamespace(session=session, user=user)
    with patch("app.routers.auth.get_supabase", return_value=sb):
        res = client.post("/auth/verify-otp", json={"phone": "0501234567", "token": "123456"})
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"] == "acc"
    assert body["refresh_token"] == "ref"
    assert body["token_type"] == "bearer"
    assert body["user_id"] == "uid-1"


def test_verify_otp_invalid_code_returns_400() -> None:
    sb = MagicMock()
    sb.auth.verify_otp.side_effect = _GotrueError(403)
    with patch("app.routers.auth.get_supabase", return_value=sb):
        res = client.post("/auth/verify-otp", json={"phone": "0501234567", "token": "000000"})
    assert res.status_code == 400


def test_verify_otp_without_session_returns_400() -> None:
    sb = MagicMock()
    sb.auth.verify_otp.return_value = SimpleNamespace(session=None, user=None)
    with patch("app.routers.auth.get_supabase", return_value=sb):
        res = client.post("/auth/verify-otp", json={"phone": "0501234567", "token": "123456"})
    assert res.status_code == 400


# ── get_current_user dependency ──────────────────────────────────────────────


def test_get_current_user_missing_header() -> None:
    with pytest.raises(HTTPException) as exc:
        get_current_user(None)
    assert exc.value.status_code == 401


def test_get_current_user_non_bearer_scheme() -> None:
    with pytest.raises(HTTPException) as exc:
        get_current_user("Basic abc123")
    assert exc.value.status_code == 401


def test_get_current_user_empty_bearer_value() -> None:
    with pytest.raises(HTTPException) as exc:
        get_current_user("Bearer    ")
    assert exc.value.status_code == 401


def test_get_current_user_response_without_user() -> None:
    sb = MagicMock()
    sb.auth.get_user.return_value = SimpleNamespace(user=None)
    with patch("app.dependencies.get_supabase", return_value=sb):
        with pytest.raises(HTTPException) as exc:
            get_current_user("Bearer token")
    assert exc.value.status_code == 401


def test_get_current_user_invalid_token() -> None:
    sb = MagicMock()
    sb.auth.get_user.side_effect = Exception("invalid jwt")
    with patch("app.dependencies.get_supabase", return_value=sb):
        with pytest.raises(HTTPException) as exc:
            get_current_user("Bearer bad-token")
    assert exc.value.status_code == 401


def test_get_current_user_valid_token() -> None:
    sb = MagicMock()
    sb.auth.get_user.return_value = SimpleNamespace(user=SimpleNamespace(id="uid-9"))
    with patch("app.dependencies.get_supabase", return_value=sb):
        user = get_current_user("Bearer good-token")
    assert user.id == "uid-9"
    assert user.access_token == "good-token"


# ── get_authed_supabase dependency ───────────────────────────────────────────


def test_get_authed_supabase_applies_jwt() -> None:
    fake_client = MagicMock()
    with patch("app.dependencies.create_client", return_value=fake_client):
        result = get_authed_supabase(CurrentUser(id="uid", access_token="tok"))
    fake_client.postgrest.auth.assert_called_once_with("tok")
    assert result is fake_client


# ── End-to-end: a protected route rejects an unauthenticated caller ──────────


def test_booking_route_requires_auth() -> None:
    # No Authorization header -> get_current_user raises before any DB call.
    res = client.post("/bookings/lock", json={"slot_id": "s1"})
    assert res.status_code == 401
