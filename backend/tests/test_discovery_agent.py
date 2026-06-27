"""Unit tests for the Discovery Agent (Google Maps + OpenAI + Supabase mocked out)."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agents.discovery_agent import MENS_FILTER_TOOL, DiscoveryAgent


def _agent(is_mens: bool = True) -> DiscoveryAgent:
    agent = DiscoveryAgent.__new__(DiscoveryAgent)  # skip __init__ (no real clients)
    agent.settings = SimpleNamespace(google_maps_api_key="test")
    agent.db = MagicMock()
    agent.gmaps = MagicMock()
    agent.openai = _fake_openai(is_mens)
    return agent


def _fake_openai(is_mens: bool) -> MagicMock:
    """Mock AsyncOpenAI returning a forced classify_barbershop tool call."""
    arguments = '{"is_mens_barbershop": %s}' % ("true" if is_mens else "false")
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=arguments))
    message = SimpleNamespace(tool_calls=[tool_call])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

    async def fake_create(**kwargs: object) -> SimpleNamespace:
        return response

    openai = MagicMock()
    openai.chat.completions.create = fake_create
    return openai


# ── _upsert (sync, unchanged) ────────────────────────────────────────────────


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


def test_upsert_stores_filtered_google_reviews() -> None:
    agent = _agent()
    # upsert_barbershop RPC returns the new row's uuid as a scalar.
    agent.db.rpc.return_value.execute.return_value = SimpleNamespace(data="shop-1")
    place = {
        "place_id": "PID",
        "name": "Shop",
        "geometry": {"location": {"lat": 1, "lng": 2}},
        "reviews": [
            {"author_name": "Avi", "rating": 5, "text": "Great fade"},  # kept
            {"author_name": "Anonymous", "rating": 5, "text": "meh"},  # dropped (generic)
            {"author_name": "Dana", "rating": 4, "text": "   "},  # dropped (empty)
        ],
    }
    agent._upsert(place)

    review_calls = [c for c in agent.db.rpc.call_args_list if c[0][0] == "upsert_external_review"]
    assert len(review_calls) == 1
    args = review_calls[0][0][1]
    assert args["p_barbershop_id"] == "shop-1"
    assert args["p_author"] == "Avi"
    assert args["p_reviewed_at"] is None  # relative time not stored as timestamptz


def test_upsert_no_reviews_no_review_calls() -> None:
    agent = _agent()
    agent.db.rpc.return_value.execute.return_value = SimpleNamespace(data="shop-1")
    agent._upsert(
        {"place_id": "PID", "name": "Shop", "geometry": {"location": {"lat": 1, "lng": 2}}}
    )
    assert not [c for c in agent.db.rpc.call_args_list if c[0][0] == "upsert_external_review"]


def test_upsert_skips_when_geometry_missing() -> None:
    agent = _agent()
    agent._upsert({"place_id": "PID2", "name": "No Geo"})  # no geometry
    agent.db.rpc.assert_not_called()


def test_upsert_defaults_missing_name() -> None:
    agent = _agent()
    agent._upsert({"place_id": "PID3", "geometry": {"location": {"lat": 1, "lng": 2}}})
    assert agent.db.rpc.call_args[0][1]["p_name"] == "Unknown"


def test_upsert_patches_opening_hours_when_present() -> None:
    agent = _agent()
    place = {
        "geometry": {"location": {"lat": 32.0, "lng": 34.7}},
        "place_id": "pid-1",
        "name": "Shop",
        "opening_hours": {"weekday_text": ["Mon 9-5"], "periods": [], "open_now": True},
    }
    agent._upsert(place)
    # The opening_hours jsonb is patched via a separate table().update() call.
    agent.db.table.assert_called_with("barbershops")
    update_arg = agent.db.table.return_value.update.call_args[0][0]
    assert update_arg["opening_hours"]["open_now"] is True
    assert update_arg["opening_hours"]["weekday_text"] == ["Mon 9-5"]


# ── MENS_FILTER_TOOL schema ──────────────────────────────────────────────────


def test_mens_filter_tool_schema_shape() -> None:
    fn = MENS_FILTER_TOOL["function"]
    assert fn["name"] == "classify_barbershop"
    params = fn["parameters"]
    assert "is_mens_barbershop" in params["properties"]
    assert params["required"] == ["is_mens_barbershop"]


# ── _is_mens_barbershop classifier ───────────────────────────────────────────


def test_is_mens_barbershop_true() -> None:
    agent = _agent(is_mens=True)
    place = {"name": "Men's Cuts", "types": ["barber_shop"], "reviews": [{"text": "great fade"}]}
    assert asyncio.run(agent._is_mens_barbershop(place)) is True


def test_is_mens_barbershop_false() -> None:
    agent = _agent(is_mens=False)
    assert asyncio.run(agent._is_mens_barbershop({"name": "Nails Spa"})) is False


def test_is_mens_barbershop_fails_closed_on_error() -> None:
    agent = _agent()

    async def boom(**kwargs: object) -> object:
        raise RuntimeError("openai down")

    agent.openai.chat.completions.create = boom
    assert asyncio.run(agent._is_mens_barbershop({"name": "Mystery"})) is False


# ── discover() pipeline ──────────────────────────────────────────────────────


def _single_place_agent(is_mens: bool) -> DiscoveryAgent:
    agent = _agent(is_mens=is_mens)
    agent.gmaps.places_nearby.return_value = {"results": [{"place_id": "PID"}]}
    agent.gmaps.place.return_value = {
        "result": {
            "place_id": "PID",
            "name": "Some Shop",
            "geometry": {"location": {"lat": 1, "lng": 2}},
        }
    }
    return agent


def test_discover_upserts_confirmed_mens_shop() -> None:
    agent = _single_place_agent(is_mens=True)
    total = asyncio.run(agent.discover(32.0, 34.0, radius_m=1000))
    assert total == 1
    upserts = [c for c in agent.db.rpc.call_args_list if c[0][0] == "upsert_barbershop"]
    assert len(upserts) == 1


def test_discover_skips_non_mens_shop() -> None:
    agent = _single_place_agent(is_mens=False)
    total = asyncio.run(agent.discover(32.0, 34.0, radius_m=1000))
    assert total == 0
    agent.db.rpc.assert_not_called()


def test_discover_deduplicates_place_ids_across_types() -> None:
    agent = _agent(is_mens=True)
    # Same place returned for both place types -> classified + upserted once.
    agent.gmaps.places_nearby.return_value = {"results": [{"place_id": "DUP"}]}
    agent.gmaps.place.return_value = {
        "result": {
            "place_id": "DUP",
            "name": "Dup Shop",
            "geometry": {"location": {"lat": 1, "lng": 2}},
        }
    }

    total = asyncio.run(agent.discover(32.0, 34.0, radius_m=1000))

    assert total == 1
    upserts = [c for c in agent.db.rpc.call_args_list if c[0][0] == "upsert_barbershop"]
    assert len(upserts) == 1


def test_discover_skips_results_without_place_id() -> None:
    agent = _agent()
    agent.gmaps.places_nearby.return_value = {"results": [{}, {"name": "no id"}]}
    total = asyncio.run(agent.discover(32.0, 34.0, radius_m=1000))
    assert total == 0
    agent.gmaps.place.assert_not_called()


def test_discover_isolates_per_place_fetch_errors() -> None:
    agent = _agent()
    agent.gmaps.places_nearby.return_value = {"results": [{"place_id": "ERR"}]}
    agent.gmaps.place.side_effect = Exception("details failed")
    # Fetch error on the single place is caught -> no candidates, count 0.
    assert asyncio.run(agent.discover(32.0, 34.0, radius_m=1000)) == 0


def test_run_module_entry_delegates_to_discover() -> None:
    from unittest.mock import patch

    from app.agents import discovery_agent

    async def fake_discover(*args: object) -> int:
        return 5

    with patch.object(discovery_agent, "DiscoveryAgent") as Agent:
        Agent.return_value.discover.side_effect = fake_discover
        out = discovery_agent.run(31.0, 35.0, 4000)
    assert out == 5
    Agent.return_value.discover.assert_called_once_with(31.0, 35.0, 4000)
