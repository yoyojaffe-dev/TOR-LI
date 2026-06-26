"""Unit tests for the Scraping Agent (Playwright/OpenAI mocked out)."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.agents.scraping_agent import (
    SLOT_EXTRACTION_TOOL,
    ScrapingAgent,
    _is_skippable_url,
)


# ── URL skip filter ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.facebook.com/somebarber", True),
        ("https://instagram.com/barber", True),
        ("https://t.me/barber", True),
        ("https://ok-barber.co.il/", False),
        ("https://yullia.com/branches/x", False),
        ("", False),
    ],
)
def test_is_skippable_url(url: str, expected: bool) -> None:
    assert _is_skippable_url(url) is expected


# ── OpenAI function-calling schema ───────────────────────────────────────────

def test_slot_extraction_tool_schema_shape() -> None:
    fn = SLOT_EXTRACTION_TOOL["function"]
    assert fn["name"] == "extract_slots"
    item = fn["parameters"]["properties"]["slots"]["items"]
    assert set(item["required"]) == {"service_name", "slot_time"}
    assert "price" in item["properties"]


# ── Agent helpers with mocked clients ────────────────────────────────────────

def _agent() -> ScrapingAgent:
    agent = ScrapingAgent.__new__(ScrapingAgent)  # skip __init__ (no real clients)
    agent.settings = SimpleNamespace(openai_api_key="test")
    agent.db = MagicMock()
    agent.openai = MagicMock()
    return agent


def test_fetch_targets_filters_out_social_urls() -> None:
    agent = _agent()
    rows = [
        {"id": "1", "name": "Real", "booking_url": "https://ok-barber.co.il/"},
        {"id": "2", "name": "FB", "booking_url": "https://facebook.com/x"},
    ]
    agent.db.table.return_value.select.return_value.not_.is_.return_value.execute.return_value = (
        SimpleNamespace(data=rows)
    )
    targets = agent.fetch_targets()
    assert [t["id"] for t in targets] == ["1"]


def test_fetch_targets_handles_empty() -> None:
    agent = _agent()
    agent.db.table.return_value.select.return_value.not_.is_.return_value.execute.return_value = (
        SimpleNamespace(data=None)
    )
    assert agent.fetch_targets() == []


def test_sync_slots_one_rpc_per_slot() -> None:
    agent = _agent()
    slots = [
        {"service_name": "Cut", "slot_time": "2026-06-26T09:00:00+03:00", "price": 80},
        {"service_name": "Fade", "slot_time": "2026-06-26T10:00:00+03:00"},  # no price
    ]
    written = agent._sync_slots("shop-1", slots)
    assert written == 2
    assert agent.db.rpc.call_count == 2
    name, args = agent.db.rpc.call_args_list[0][0]
    assert name == "upsert_free_slot"
    assert args["p_barbershop_id"] == "shop-1"
    assert args["p_price"] == 80
    # Second slot omits price -> None passed through.
    assert agent.db.rpc.call_args_list[1][0][1]["p_price"] is None


def test_sync_slots_empty_writes_nothing() -> None:
    agent = _agent()
    assert agent._sync_slots("shop-1", []) == 0
    agent.db.rpc.assert_not_called()


def test_sync_slots_continues_after_per_slot_error() -> None:
    agent = _agent()
    # First rpc raises, second succeeds -> only 1 counted, loop not aborted.
    agent.db.rpc.side_effect = [Exception("boom"), MagicMock()]
    slots = [
        {"service_name": "Cut", "slot_time": "2026-06-26T09:00:00+03:00"},
        {"service_name": "Fade", "slot_time": "2026-06-26T10:00:00+03:00"},
    ]
    assert agent._sync_slots("shop-1", slots) == 1


def test_parse_html_returns_extracted_slots() -> None:
    agent = _agent()
    payload = {"slots": [{"service_name": "Cut", "slot_time": "2026-06-26T09:00:00+03:00", "price": 80}]}
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(payload)))
    message = SimpleNamespace(tool_calls=[tool_call])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

    async def fake_create(**kwargs):
        return response

    agent.openai.chat.completions.create = fake_create
    result = asyncio.run(agent.parse_html("page text", "Test Barber"))
    assert result == payload["slots"]


def test_parse_html_empty_slots() -> None:
    agent = _agent()
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps({"slots": []})))
    message = SimpleNamespace(tool_calls=[tool_call])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

    async def fake_create(**kwargs):
        return response

    agent.openai.chat.completions.create = fake_create
    assert asyncio.run(agent.parse_html("nothing here", "Empty Shop")) == []
