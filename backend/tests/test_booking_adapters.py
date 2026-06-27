"""Tests for per-platform booking adapters: detection, routing, fill/submit, fallback."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agents.booking_adapters import (
    GenericAIAdapter,
    GlameraAdapter,
    Tor4YouAdapter,
    detect_platform,
    get_adapter,
)
from app.agents.booking_adapters.generic_ai import BOOKING_FORM_TOOL

# ── Fake Playwright page ─────────────────────────────────────────────────────


class _FakePage:
    """Minimal async page: records fills/clicks, returns canned html/body."""

    def __init__(self, html: str = "<form></form>", body_text: str = "") -> None:
        self._html = html
        self._body = body_text
        self.filled: list[tuple[str, str]] = []
        self.clicked: list[str] = []

    async def content(self) -> str:
        return self._html

    async def fill(self, selector: str, value: str) -> None:
        self.filled.append((selector, value))

    async def click(self, selector: str) -> None:
        self.clicked.append(selector)

    async def wait_for_timeout(self, ms: int) -> None:
        return None

    async def inner_text(self, selector: str) -> str:
        return self._body


def _fake_openai(plan: dict) -> MagicMock:
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(plan)))
    message = SimpleNamespace(tool_calls=[tool_call])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

    async def fake_create(**kwargs: object) -> SimpleNamespace:
        return response

    openai = MagicMock()
    openai.chat.completions.create = fake_create
    return openai


_CTX = {"id": "slot-1", "slot_time": "2026-06-28T10:00:00+03:00"}


# ── detect_platform ──────────────────────────────────────────────────────────


def test_detect_known_platforms() -> None:
    assert detect_platform("https://book.tor4you.co.il/shop/123") == "tor4you"
    assert detect_platform("https://app.glamera.com/x") == "glamera"
    assert detect_platform("https://booksy.com/en/s/123") == "booksy"


def test_detect_unknown_is_custom() -> None:
    assert detect_platform("https://some-barber.example/book") == "custom"
    assert detect_platform(None) == "custom"
    assert detect_platform("not a url") == "custom"


# ── get_adapter routing ──────────────────────────────────────────────────────


def test_get_adapter_routes_to_static() -> None:
    oa = MagicMock()
    assert isinstance(get_adapter("https://x.tor4you.co.il/a", oa), Tor4YouAdapter)
    assert isinstance(get_adapter("https://x.glamera.com/a", oa), GlameraAdapter)


def test_get_adapter_falls_back_to_ai() -> None:
    oa = MagicMock()
    # booksy has no static adapter yet -> AI fallback; so does a custom site.
    assert isinstance(get_adapter("https://booksy.com/a", oa), GenericAIAdapter)
    assert isinstance(get_adapter("https://custom.example/a", oa), GenericAIAdapter)


# ── static adapters fill + submit ────────────────────────────────────────────


def test_tor4you_adapter_fills_and_submits_live() -> None:
    page = _FakePage(body_text="התור נקבע בהצלחה — confirmed")
    result = asyncio.run(
        Tor4YouAdapter().submit(page, _CTX, "דנה", "050", live=True)  # type: ignore[arg-type]
    )
    assert result["success"] is True
    assert result["platform"] == "tor4you"
    assert page.filled == [
        (Tor4YouAdapter.NAME_SELECTOR, "דנה"),
        (Tor4YouAdapter.PHONE_SELECTOR, "050"),
    ]
    assert page.clicked == [Tor4YouAdapter.SUBMIT_SELECTOR]


def test_glamera_adapter_dry_run_skips_submit() -> None:
    page = _FakePage()
    result = asyncio.run(
        GlameraAdapter().submit(page, _CTX, "Dana", "050", live=False)  # type: ignore[arg-type]
    )
    assert result["dry_run"] is True
    assert result["platform"] == "glamera"
    assert page.filled == [
        (GlameraAdapter.NAME_SELECTOR, "Dana"),
        (GlameraAdapter.PHONE_SELECTOR, "050"),
    ]
    assert page.clicked == []  # never submitted


def test_static_adapter_not_confirmed_when_keyword_absent() -> None:
    page = _FakePage(body_text="totally unrelated page")
    result = asyncio.run(
        Tor4YouAdapter().submit(page, _CTX, "Dana", "050", live=True)  # type: ignore[arg-type]
    )
    assert result["success"] is False
    assert result["confirmed"] is False


# ── generic AI adapter (fallback) ────────────────────────────────────────────


def test_generic_ai_adapter_maps_then_submits() -> None:
    plan = {
        "fields": [
            {"selector": "#fullname", "value": "דנה"},
            {"selector": "#phone", "value": "050"},
        ],
        "submit_selector": "#confirmBtn",
        "confirmation_keywords": ["אושרה"],
    }
    adapter = GenericAIAdapter(_fake_openai(plan))
    page = _FakePage(html="<form>...</form>", body_text="ההזמנה אושרה")
    result = asyncio.run(
        adapter.submit(page, _CTX, "דנה", "050", live=True)  # type: ignore[arg-type]
    )
    assert result["success"] is True
    assert result["platform"] == "custom"
    assert page.filled == [("#fullname", "דנה"), ("#phone", "050")]
    assert page.clicked == ["#confirmBtn"]


def test_booking_form_tool_schema_shape() -> None:
    fn = BOOKING_FORM_TOOL["function"]
    assert fn["name"] == "fill_booking_form"
    assert fn["parameters"]["required"] == ["fields", "submit_selector"]
