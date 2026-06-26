"""Unit tests for the Discovery Agent (Google Maps + Supabase mocked out)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agents.discovery_agent import DiscoveryAgent


def _agent() -> DiscoveryAgent:
    agent = DiscoveryAgent.__new__(DiscoveryAgent)  # skip __init__ (no real clients)
    agent.settings = SimpleNamespace(google_maps_api_key="test")
    agent.db = MagicMock()
    agent.gmaps = MagicMock()
    return agent


def test_upsert_sends_expected_rpc_payload() -> None:
    agent = _agent()
    place = {
        "place_id": "PID1",
        "name": "Cool Cuts",
        "formatted_address": "1 Main St",
        "formatted_phone_number": "03-1234567",
        "website": "https://coolcuts.example",
        "geometry": {"location": {"lat": 32.1, "lng": 34.8}},
    }
    agent._upsert(place)

    name, args = agent.db.rpc.call_args[0]
    assert name == "upsert_barbershop"
    assert args["p_google_place_id"] == "PID1"
    assert args["p_name"] == "Cool Cuts"
    assert args["p_lat"] == 32.1
    assert args["p_lng"] == 34.8
    assert args["p_booking_url"] == "https://coolcuts.example"


def test_upsert_skips_when_geometry_missing() -> None:
    agent = _agent()
    agent._upsert({"place_id": "PID2", "name": "No Geo"})  # no geometry
    agent.db.rpc.assert_not_called()


def test_upsert_defaults_missing_name() -> None:
    agent = _agent()
    agent._upsert({"place_id": "PID3", "geometry": {"location": {"lat": 1, "lng": 2}}})
    assert agent.db.rpc.call_args[0][1]["p_name"] == "Unknown"


def test_discover_deduplicates_place_ids_across_types() -> None:
    agent = _agent()
    # Same place returned for both place types -> upserted once.
    nearby = {"results": [{"place_id": "DUP"}]}  # no next_page_token -> single page
    agent.gmaps.places_nearby.return_value = nearby
    agent.gmaps.place.return_value = {
        "result": {"place_id": "DUP", "name": "Dup Shop",
                   "geometry": {"location": {"lat": 1, "lng": 2}}}
    }

    total = agent.discover(32.0, 34.0, radius_m=1000)

    # _PLACE_TYPES has 2 entries but DUP is seen once -> 1 upsert, count 1.
    assert total == 1
    upserts = [c for c in agent.db.rpc.call_args_list if c[0][0] == "upsert_barbershop"]
    assert len(upserts) == 1


def test_discover_skips_results_without_place_id() -> None:
    agent = _agent()
    agent.gmaps.places_nearby.return_value = {"results": [{}, {"name": "no id"}]}
    total = agent.discover(32.0, 34.0, radius_m=1000)
    assert total == 0
    agent.gmaps.place.assert_not_called()


def test_discover_isolates_per_place_errors() -> None:
    agent = _agent()
    agent.gmaps.places_nearby.return_value = {"results": [{"place_id": "ERR"}]}
    agent.gmaps.place.side_effect = Exception("details failed")
    # Error on the single place is caught -> count stays 0, no crash.
    assert agent.discover(32.0, 34.0, radius_m=1000) == 0
