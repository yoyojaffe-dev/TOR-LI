"""Tests for app-level middleware + router mounting."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_unhandled_error_becomes_safe_500() -> None:
    """An unexpected exception in a handler is converted to a generic 500 by the
    logging middleware — the internal error message must not leak to the client."""
    client = TestClient(app, raise_server_exceptions=False)
    with patch(
        "app.routers.bookings.locking.list_bookings",
        side_effect=RuntimeError("secret internal detail"),
    ):
        res = client.get("/bookings", params={"user_token": "u1"})
    assert res.status_code == 500
    assert res.json() == {"detail": "internal server error"}
    assert "secret internal detail" not in res.text


def test_request_logging_middleware_logs_status(caplog) -> None:  # type: ignore[no-untyped-def]
    """The middleware emits one info log line per request with method/path/status."""
    client = TestClient(app)
    with caplog.at_level("INFO", logger="torli.api"):
        res = client.get("/health")
    assert res.status_code == 200
    assert any("GET /health -> 200" in m for m in caplog.messages)


def test_admin_router_mounted_in_development() -> None:
    """Admin endpoints are mounted in non-production environments (env=development
    in tests). Uses the OpenAPI schema, which lists real paths across versions."""
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    assert "/admin/discovery/run" in schema["paths"]
