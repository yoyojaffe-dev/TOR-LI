"""Unit tests for the Booking Agent (Playwright + OpenAI mocked out)."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from app.agents.booking_agent import BOOKING_FORM_TOOL, BookingAgent


def _agent(booking_live: bool = True) -> BookingAgent:
    agent = BookingAgent.__new__(BookingAgent)  # skip __init__ (no real clients)
    agent.settings = SimpleNamespace(booking_live=booking_live)
    agent.db = MagicMock()
    agent.openai = MagicMock()
    return agent


def _fake_openai(plan: dict) -> MagicMock:
    """Mock AsyncOpenAI returning a forced fill_booking_form tool call."""
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(plan)))
    message = SimpleNamespace(tool_calls=[tool_call])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

    async def fake_create(**kwargs: object) -> SimpleNamespace:
        return response

    openai = MagicMock()
    openai.chat.completions.create = fake_create
    return openai


# ── Fake Playwright page/context/browser ─────────────────────────────────────


class _FakePage:
    def __init__(self, html: str = "<form></form>", body_text: str = "") -> None:
        self._html = html
        self._body = body_text
        self.filled: list[tuple[str, str]] = []
        self.clicked: list[str] = []

    async def goto(self, url: str, **kwargs: object) -> None:
        return None

    async def wait_for_timeout(self, ms: int) -> None:
        return None

    async def content(self) -> str:
        return self._html

    async def fill(self, selector: str, value: str) -> None:
        self.filled.append((selector, value))

    async def click(self, selector: str) -> None:
        self.clicked.append(selector)

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


# ── Schema ───────────────────────────────────────────────────────────────────


def test_booking_form_tool_schema_shape() -> None:
    fn = BOOKING_FORM_TOOL["function"]
    assert fn["name"] == "fill_booking_form"
    props = fn["parameters"]["properties"]
    assert "fields" in props and "submit_selector" in props
    assert fn["parameters"]["required"] == ["fields", "submit_selector"]


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


def _patch_context(agent: BookingAgent, ctx: dict) -> None:
    # _fetch_slot_context is sync + wrapped in to_thread; patch the sync method.
    agent._fetch_slot_context = lambda slot_id: ctx  # type: ignore[method-assign]


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


# ── _book_on_page (fully live) ───────────────────────────────────────────────


def test_book_on_page_live_submit_confirmed() -> None:
    agent = _agent(booking_live=True)
    agent.openai = _fake_openai(
        {
            "fields": [
                {"selector": "#name", "value": "Dana"},
                {"selector": "#phone", "value": "050"},
            ],
            "submit_selector": "#submit",
            "confirmation_keywords": ["confirmed"],
        }
    )
    page = _FakePage(html="<form>...</form>", body_text="Booking CONFIRMED, thanks")
    browser = _FakeBrowser(page)

    result = asyncio.run(
        agent._book_on_page(browser, "https://book.example", "slot-1", "Dana", "050", "t")  # type: ignore[arg-type]
    )
    assert result["success"] is True
    assert result["confirmed"] is True
    assert page.filled == [("#name", "Dana"), ("#phone", "050")]
    assert page.clicked == ["#submit"]
    assert browser._ctx.closed is True


def test_book_on_page_live_submit_not_confirmed() -> None:
    agent = _agent(booking_live=True)
    agent.openai = _fake_openai(
        {"fields": [], "submit_selector": "#go", "confirmation_keywords": ["yay"]}
    )
    page = _FakePage(body_text="some unrelated page text")
    browser = _FakeBrowser(page)

    result = asyncio.run(
        agent._book_on_page(browser, "https://book.example", "slot-1", "Dana", "050", "t")  # type: ignore[arg-type]
    )
    assert result["success"] is False
    assert result["confirmed"] is False
    assert page.clicked == ["#go"]


def test_book_on_page_dry_run_skips_submit() -> None:
    agent = _agent(booking_live=False)
    agent.openai = _fake_openai(
        {"fields": [{"selector": "#name", "value": "Dana"}], "submit_selector": "#submit"}
    )
    page = _FakePage()
    browser = _FakeBrowser(page)

    result = asyncio.run(
        agent._book_on_page(browser, "https://book.example", "slot-1", "Dana", "050", "t")  # type: ignore[arg-type]
    )
    assert result["success"] is True
    assert result["dry_run"] is True
    assert page.filled == [("#name", "Dana")]
    assert page.clicked == []  # never submitted


def test_book_on_page_no_submit_selector_when_live_fails() -> None:
    agent = _agent(booking_live=True)
    agent.openai = _fake_openai({"fields": [], "submit_selector": ""})
    page = _FakePage()
    browser = _FakeBrowser(page)

    result = asyncio.run(
        agent._book_on_page(browser, "https://book.example", "slot-1", "Dana", "050", "t")  # type: ignore[arg-type]
    )
    assert result["success"] is False
    assert result["reason"] == "no submit selector"


def test_submit_isolates_browser_errors(monkeypatch: "MonkeyPatch") -> None:
    """A Playwright error inside submit() is caught -> success False."""
    agent = _agent()
    _patch_context(agent, {"barbershops": {"booking_url": "https://book.example"}})

    async def boom(*args: object, **kwargs: object) -> dict:
        raise RuntimeError("browser crashed")

    # _book_on_page is where the real work happens; make it raise to exercise
    # submit()'s try/except/finally (browser still gets closed).
    agent._book_on_page = boom  # type: ignore[method-assign]

    class _PW:
        class chromium:
            @staticmethod
            async def launch(**kwargs: object) -> MagicMock:
                browser = MagicMock()

                async def _close() -> None:
                    return None

                browser.close = _close
                return browser

        async def __aenter__(self) -> "_PW":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr("app.agents.booking_agent.async_playwright", lambda: _PW())

    result = asyncio.run(agent.submit("slot-1", "Dana", "050"))
    assert result["success"] is False
    assert "browser crashed" in result["reason"]
