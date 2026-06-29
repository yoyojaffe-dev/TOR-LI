"""Geocode endpoint — Google Maps SDK mocked (no network)."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _settings(key: str = "test-key") -> MagicMock:
    s = MagicMock()
    s.google_maps_api_key = key
    return s


def test_geocode_success() -> None:
    gmaps = MagicMock()
    gmaps.geocode.return_value = [
        {"geometry": {"location": {"lat": 32.0919, "lng": 34.7947}}, "formatted_address": "כצנלסון 88, תל אביב"}
    ]
    with (
        patch("app.routers.geocode.googlemaps.Client", return_value=gmaps),
        patch("app.routers.geocode.get_settings", return_value=_settings()),
    ):
        res = client.get("/geocode", params={"address": "katzenelson 88 tel aviv"})
    assert res.status_code == 200
    body = res.json()
    assert body["lat"] == 32.0919
    assert body["lng"] == 34.7947
    assert body["formatted_address"].startswith("כצנלסון")


def test_geocode_not_found() -> None:
    gmaps = MagicMock()
    gmaps.geocode.return_value = []
    with (
        patch("app.routers.geocode.googlemaps.Client", return_value=gmaps),
        patch("app.routers.geocode.get_settings", return_value=_settings()),
    ):
        res = client.get("/geocode", params={"address": "zzzzz nowhere"})
    assert res.status_code == 404


def test_geocode_not_configured() -> None:
    with patch("app.routers.geocode.get_settings", return_value=_settings(key="")):
        res = client.get("/geocode", params={"address": "tel aviv"})
    assert res.status_code == 503
