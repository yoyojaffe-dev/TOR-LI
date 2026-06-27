"""Unit tests for the Booking Agent orchestrator (adapter selection + guards).

Per-platform fill/submit logic is covered in tests/test_booking_adapters.py;
here we test slot lookup, the URL guards, browser lifecycle, and that submit()
routes the loaded page to the adapter chosen by get_adapter().
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from app.agents.booking_agent import BookingAgent


def _agent(booking_live: bool = True) -> BookingAgent:
    agent = BookingAgent.__new__(BookingAgent)  # skip __init__ (no real clients)
    agent.settings = SimpleNamespace(booking_live=booking_live)
    agent.db = MagicMock()
    agent.openai = MagicMock()
    return agent


def _patch_context(agent: BookingAgent, ctx: dict) -> None:
    # _fetch_slot_context is sync + wrapped in to_thread; patch the sync method.
    agent._fetch_slot_context = lambda slot_id: ctx  # type: ignore[method-assign]


# ── Fake Playwright stack ────────────────────────────────────────────────────


class _FakePage:
    def __init__(self) -> None:
        self.goto_args: tuple[str, ...] = ()

    async def goto(self, url: str, **kwargs: object) -> None:
        self.goto_args = (url,)

    async def wait_for_timeout(self, ms: int) -> None:
        return None


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.closed = False

    async def new_page(self) -> _FakePage:
        return self._page

    async def close(self) -> None:
        self.closed = True


class _FakeBrowser:
    def __init__(self, ctx: _FakeContext) -> None:
        self._ctx = ctx
        self.closed = False

    async def new_context(self, **kwargs: object) -> _FakeContext:
        return self._ctx

    async def close(self) -> None:
        self.closed = True


class _FakePW:
    def __init__(self, browser: _FakeBrowser) -> None:
        self._browser = browser

        async def _launch(**kwargs: object) -> _FakeBrowser:
            return browser

        self.chromium = SimpleNamespace(launch=_launch)

    async def __aenter__(self) -> "_FakePW":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _install_fake_pw(monkeypatch: MonkeyPatch) -> tuple[_FakePage, _FakeBrowser]:
    page = _FakePage()
    ctx = _FakeContext(page)
    browser = _FakeBrowser(ctx)
    monkeypatch.setattr("app.agents.booking_agent.async_playwright", lambda: _FakePW(browser))
    return page, browser


# ── _fetch_slot_context ──────────────────────────────────────────────────────


def test_fetch_slot_context_returns_joined_row() -> None:
    agent = _agent()
    row = {
        "id": "slot-1",
        "service_name": "Cut",
        "slot_time": "2026-06-28T10:00:00+03:00",
        "barbershops": {"name": "Cool Cuts", "booking_url": "https://book.example"},
    }
    agent.db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(  # noqa: E501
        data=[row]
    )
    ctx = agent._fetch_slot_context("slot-1")
    assert ctx["barbershops"]["booking_url"] == "https://book.example"


# ── submit() guards ──────────────────────────────────────────────────────────


def test_submit_fails_when_slot_missing() -> None:
    agent = _agent()
    _patch_context(agent, {})
    result = asyncio.run(agent.submit("slot-x", "Dana", "+972500000000"))
    assert result["success"] is False
    assert result["reason"] == "slot not found"


def test_submit_fails_when_no_booking_url() -> None:
    agent = _agent()
    _patch_context(agent, {"barbershops": {"name": "No URL"}})
    result = asyncio.run(agent.submit("slot-1", "Dana", "+972500000000"))
    assert result["success"] is False
    assert result["reason"] == "no booking_url"


def test_submit_fails_on_skippable_url() -> None:
    agent = _agent()
    _patch_context(agent, {"barbershops": {"booking_url": "https://facebook.com/shop"}})
    result = asyncio.run(agent.submit("slot-1", "Dana", "+972500000000"))
    assert result["success"] is False
    assert result["reason"] == "unsupported booking site"


# ── adapter routing ──────────────────────────────────────────────────────────


def test_submit_routes_page_to_selected_adapter(monkeypatch: MonkeyPatch) -> None:
    agent = _agent(booking_live=True)
    _patch_context(
        agent, {"id": "slot-1", "barbershops": {"booking_url": "https://x.tor4you.co.il/a"}}
    )
    page, browser = _install_fake_pw(monkeypatch)

    seen: dict[str, object] = {}

    class _FakeAdapter:
        platform = "tor4you"

        async def submit(self, pg, ctx, name, phone, *, live):  # type: ignore[no-untyped-def]
            seen.update(page=pg, name=name, phone=phone, live=live)
            return {"success": True, "platform": self.platform, "slot_id": ctx["id"]}

    monkeypatch.setattr("app.agents.booking_agent.get_adapter", lambda url, openai: _FakeAdapter())

    result = asyncio.run(agent.submit("slot-1", "Dana", "050"))
    assert result == {"success": True, "platform": "tor4you", "slot_id": "slot-1"}
    assert seen["page"] is page  # the loaded page was handed to the adapter
    assert seen["live"] is True
    assert page.goto_args == ("https://x.tor4you.co.il/a",)
    assert browser.closed is True  # browser cleaned up


def test_submit_isolates_adapter_errors(monkeypatch: MonkeyPatch) -> None:
    agent = _agent()
    _patch_context(agent, {"id": "slot-1", "barbershops": {"booking_url": "https://book.example"}})
    _install_fake_pw(monkeypatch)

    class _BoomAdapter:
        platform = "custom"

        async def submit(self, *a: object, **k: object) -> dict:
            raise RuntimeError("adapter crashed")

    monkeypatch.setattr("app.agents.booking_agent.get_adapter", lambda url, openai: _BoomAdapter())

    result = asyncio.run(agent.submit("slot-1", "Dana", "050"))
    assert result["success"] is False
    assert "adapter crashed" in result["reason"]
