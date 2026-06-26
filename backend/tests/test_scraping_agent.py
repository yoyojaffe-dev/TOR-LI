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
    payload = {
        "slots": [{"service_name": "Cut", "slot_time": "2026-06-26T09:00:00+03:00", "price": 80}]
    }
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


# ── Async orchestration (Playwright mocked) ──────────────────────────────────


class _FakePage:
    """Minimal async Playwright page stub."""

    def __init__(self, body_text: str) -> None:
        self._body = body_text
        self.goto_args: tuple[str, ...] = ()

    async def goto(self, url: str, **kwargs: object) -> None:
        self.goto_args = (url,)

    async def wait_for_timeout(self, ms: int) -> None:
        return None

    async def inner_text(self, selector: str) -> str:
        return self._body


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.closed = False

    async def new_page(self) -> _FakePage:
        return self._page

    async def close(self) -> None:
        self.closed = True


class _FakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self._ctx = _FakeContext(page)

    async def new_context(self, **kwargs: object) -> _FakeContext:
        return self._ctx

    async def close(self) -> None:
        return None


def test_scrape_page_truncates_and_closes_context() -> None:
    agent = _agent()
    page = _FakePage("x" * 20_000)
    browser = _FakeBrowser(page)
    text = asyncio.run(agent.scrape_page(browser, "https://shop.example/"))  # type: ignore[arg-type]
    # Truncated to the 15k char budget, and the context was closed afterwards.
    assert len(text) == 15_000
    assert browser._ctx.closed is True
    assert page.goto_args == ("https://shop.example/",)


def test_process_shop_success_writes_slots() -> None:
    agent = _agent()
    slots = [{"service_name": "Cut", "slot_time": "2026-06-26T09:00:00+03:00", "price": 80}]

    async def fake_scrape(browser: object, url: str) -> str:
        return "page text"

    async def fake_parse(text: str, name: str) -> list[dict]:
        return slots

    agent.scrape_page = fake_scrape  # type: ignore[method-assign]
    agent.parse_html = fake_parse  # type: ignore[method-assign]
    agent._sync_slots = MagicMock(return_value=1)  # type: ignore[method-assign]

    written = asyncio.run(
        agent.process_shop(MagicMock(), {"id": "s1", "name": "Shop", "booking_url": "u"})
    )
    assert written == 1
    agent._sync_slots.assert_called_once_with("s1", slots)


def test_process_shop_no_slots_skips_sync() -> None:
    agent = _agent()

    async def fake_scrape(browser: object, url: str) -> str:
        return "page text"

    async def fake_parse(text: str, name: str) -> list[dict]:
        return []

    agent.scrape_page = fake_scrape  # type: ignore[method-assign]
    agent.parse_html = fake_parse  # type: ignore[method-assign]
    agent._sync_slots = MagicMock()  # type: ignore[method-assign]

    written = asyncio.run(
        agent.process_shop(MagicMock(), {"id": "s1", "name": "Shop", "booking_url": "u"})
    )
    assert written == 0
    agent._sync_slots.assert_not_called()


def test_process_shop_swallows_errors_returns_zero() -> None:
    agent = _agent()

    async def boom(browser: object, url: str) -> str:
        raise RuntimeError("page exploded")

    agent.scrape_page = boom  # type: ignore[method-assign]
    written = asyncio.run(
        agent.process_shop(MagicMock(), {"id": "s1", "name": "Shop", "booking_url": "u"})
    )
    assert written == 0  # error isolated per shop, not re-raised


def test_run_once_aggregates_stats(monkeypatch: "pytest.MonkeyPatch") -> None:
    agent = _agent()
    targets = [
        {"id": "1", "name": "A", "booking_url": "u1"},
        {"id": "2", "name": "B", "booking_url": "u2"},
    ]
    agent.fetch_targets = MagicMock(return_value=targets)  # type: ignore[method-assign]

    async def fake_process(browser: object, shop: dict) -> int:
        return 3  # each shop yields 3 slots

    agent.process_shop = fake_process  # type: ignore[method-assign]

    # Stub the async_playwright() context manager + chromium.launch.
    class _PW:
        def __init__(self) -> None:
            self.chromium = SimpleNamespace(launch=self._launch)

        async def _launch(self, **kwargs: object) -> _FakeBrowser:
            return _FakeBrowser(_FakePage(""))

    class _PWCtx:
        async def __aenter__(self) -> _PW:
            return _PW()

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr("app.agents.scraping_agent.async_playwright", lambda: _PWCtx())

    stats = asyncio.run(agent.run_once())
    assert stats == {"shops_processed": 2, "slots_written": 6}


def test_run_once_bounds_concurrency(monkeypatch: "pytest.MonkeyPatch") -> None:
    """run_once never runs more than _MAX_CONCURRENT_SHOPS shops at once."""
    from app.agents import scraping_agent as mod

    agent = _agent()
    targets = [{"id": str(i), "name": f"S{i}", "booking_url": f"u{i}"} for i in range(12)]
    agent.fetch_targets = MagicMock(return_value=targets)  # type: ignore[method-assign]

    active = 0
    peak = 0

    async def fake_process(browser: object, shop: dict) -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)  # hold the slot so overlap is observable
        active -= 1
        return 1

    agent.process_shop = fake_process  # type: ignore[method-assign]

    class _PW:
        def __init__(self) -> None:
            self.chromium = SimpleNamespace(launch=self._launch)

        async def _launch(self, **kwargs: object) -> _FakeBrowser:
            return _FakeBrowser(_FakePage(""))

    class _PWCtx:
        async def __aenter__(self) -> _PW:
            return _PW()

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(mod, "async_playwright", lambda: _PWCtx())

    stats = asyncio.run(agent.run_once())
    assert stats == {"shops_processed": 12, "slots_written": 12}
    assert peak <= mod._MAX_CONCURRENT_SHOPS  # concurrency was bounded


def test_run_once_isolates_a_failing_shop(monkeypatch: "pytest.MonkeyPatch") -> None:
    """A task raising does not sink the pass; other shops' slots still count."""
    from app.agents import scraping_agent as mod

    agent = _agent()
    targets = [{"id": "ok", "booking_url": "u1"}, {"id": "bad", "booking_url": "u2"}]
    agent.fetch_targets = MagicMock(return_value=targets)  # type: ignore[method-assign]

    async def fake_process(browser: object, shop: dict) -> int:
        if shop["id"] == "bad":
            raise RuntimeError("boom")
        return 4

    agent.process_shop = fake_process  # type: ignore[method-assign]

    class _PW:
        def __init__(self) -> None:
            self.chromium = SimpleNamespace(launch=self._launch)

        async def _launch(self, **kwargs: object) -> _FakeBrowser:
            return _FakeBrowser(_FakePage(""))

    class _PWCtx:
        async def __aenter__(self) -> _PW:
            return _PW()

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(mod, "async_playwright", lambda: _PWCtx())

    stats = asyncio.run(agent.run_once())
    assert stats["shops_processed"] == 2
    assert stats["slots_written"] == 4  # only the healthy shop contributed


def test_run_once_empty_targets_short_circuits(monkeypatch: "pytest.MonkeyPatch") -> None:
    """No targets -> no browser launched, zero stats."""
    from app.agents import scraping_agent as mod

    agent = _agent()
    agent.fetch_targets = MagicMock(return_value=[])  # type: ignore[method-assign]

    launched = False

    class _PWCtx:
        async def __aenter__(self) -> object:
            nonlocal launched
            launched = True
            raise AssertionError("playwright must not start when there are no targets")

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(mod, "async_playwright", lambda: _PWCtx())

    stats = asyncio.run(agent.run_once())
    assert stats == {"shops_processed": 0, "slots_written": 0}
    assert launched is False
