"""Unit tests for the Enrichment Agent (Playwright / OpenAI / Supabase mocked)."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import app.agents.enrichment_agent as mod
from app.agents.enrichment_agent import EnrichmentAgent
from app.models.schemas import ExtractedService, ExtractedStaff, ShopEnrichment


def _agent() -> EnrichmentAgent:
    agent = EnrichmentAgent.__new__(EnrichmentAgent)
    agent.settings = SimpleNamespace(openai_api_key="test")
    agent.db = MagicMock()
    agent.openai = MagicMock()
    return agent


# ── fetch_targets ────────────────────────────────────────────────────────────


def test_fetch_targets_filters_skippable() -> None:
    agent = _agent()
    chain = agent.db.table.return_value.select.return_value.not_.is_.return_value.in_.return_value
    chain.order.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=[
            {"id": "1", "name": "A", "booking_url": "https://book.tor4you.co.il/a"},
            {"id": "2", "name": "B", "booking_url": "https://facebook.com/b"},
        ]
    )
    targets = agent.fetch_targets(50)
    assert [t["id"] for t in targets] == ["1"]  # facebook dropped


# ── enrich_shop guards ───────────────────────────────────────────────────────


def _profile_with_price() -> ShopEnrichment:
    return ShopEnrichment(
        staff=[ExtractedStaff(name="Lio")],
        services=[ExtractedService(name="Cut", category="haircut", price=60, duration_mins=30)],
    )


def test_enrich_shop_thin_content_skips_extraction() -> None:
    agent = _agent()
    extracted = {"called": False}

    async def fake_load(browser: object, url: str) -> str:
        return "too short"

    async def fake_extract(name: str, text: str) -> ShopEnrichment:
        extracted["called"] = True
        return ShopEnrichment()

    agent._load_page = fake_load  # type: ignore[method-assign]
    agent._extract = fake_extract  # type: ignore[method-assign]
    agent._persist = MagicMock()  # type: ignore[method-assign]
    agent._mark_enriched = MagicMock()  # type: ignore[method-assign]

    result = asyncio.run(
        agent.enrich_shop(MagicMock(), {"id": "s1", "name": "Shop", "booking_url": "u"})
    )
    assert result["thin"] == 1
    assert extracted["called"] is False  # OpenAI never invoked
    agent._persist.assert_not_called()
    agent._mark_enriched.assert_called_once_with("s1")  # still stamped


def test_enrich_shop_generic_page_nulls_pricing() -> None:
    agent = _agent()

    async def fake_load(browser: object, url: str) -> str:
        return "x" * 500

    async def fake_extract(name: str, text: str) -> ShopEnrichment:
        return _profile_with_price()

    agent._load_page = fake_load  # type: ignore[method-assign]
    agent._extract = fake_extract  # type: ignore[method-assign]
    agent._persist = MagicMock(return_value=(1, 1))  # type: ignore[method-assign]
    agent._mark_enriched = MagicMock()  # type: ignore[method-assign]

    # generic url -> not a pricing source -> price/duration nulled before persist
    asyncio.run(
        agent.enrich_shop(
            MagicMock(), {"id": "s1", "name": "Shop", "booking_url": "https://x.example/b"}
        )
    )
    profile = agent._persist.call_args[0][1]
    assert profile.services[0].price is None
    assert profile.services[0].duration_mins is None


def test_enrich_shop_static_platform_keeps_pricing() -> None:
    agent = _agent()

    async def fake_load(browser: object, url: str) -> str:
        return "x" * 500

    async def fake_extract(name: str, text: str) -> ShopEnrichment:
        return _profile_with_price()

    agent._load_page = fake_load  # type: ignore[method-assign]
    agent._extract = fake_extract  # type: ignore[method-assign]
    agent._persist = MagicMock(return_value=(1, 1))  # type: ignore[method-assign]
    agent._mark_enriched = MagicMock()  # type: ignore[method-assign]

    asyncio.run(
        agent.enrich_shop(
            MagicMock(), {"id": "s1", "name": "Shop", "booking_url": "https://book.tor4you.co.il/a"}
        )
    )
    profile = agent._persist.call_args[0][1]
    assert profile.services[0].price == 60  # trusted platform -> kept


def test_enrich_shop_isolates_errors() -> None:
    agent = _agent()

    async def boom(browser: object, url: str) -> str:
        raise RuntimeError("page exploded")

    agent._load_page = boom  # type: ignore[method-assign]
    result = asyncio.run(
        agent.enrich_shop(MagicMock(), {"id": "s1", "name": "Shop", "booking_url": "u"})
    )
    assert result == {"staff": 0, "services": 0, "thin": 0}


# ── _persist resolves staff_name -> staff_id ─────────────────────────────────


def test_persist_resolves_staff_id_for_services() -> None:
    agent = _agent()

    def fake_rpc(name: str, args: dict) -> MagicMock:
        exec_mock = MagicMock()
        if name == "upsert_staff":
            exec_mock.execute.return_value = SimpleNamespace(data="staff-uuid-1")
        else:
            exec_mock.execute.return_value = SimpleNamespace(data=None)
        return exec_mock

    agent.db.rpc.side_effect = fake_rpc

    profile = ShopEnrichment(
        staff=[ExtractedStaff(name="Lio")],
        services=[ExtractedService(name="Cut", staff_name="Lio")],
    )
    staff_n, services_n = agent._persist("shop-1", profile)
    assert (staff_n, services_n) == (1, 1)

    svc_call = [c for c in agent.db.rpc.call_args_list if c[0][0] == "upsert_service"][0]
    assert svc_call[0][1]["p_staff_id"] == "staff-uuid-1"  # resolved by name


def test_mark_enriched_updates_row() -> None:
    agent = _agent()
    agent._mark_enriched("shop-9")
    agent.db.table.assert_called_with("barbershops")
    update_arg = agent.db.table.return_value.update.call_args[0][0]
    assert "enriched_at" in update_arg


# ── _extract (OpenAI mocked) ─────────────────────────────────────────────────


def test_extract_parses_tool_call() -> None:
    agent = _agent()
    payload = {"staff": [{"name": "Lio"}], "services": [{"name": "Cut"}], "reviews": []}
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(payload)))
    message = SimpleNamespace(tool_calls=[tool_call])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

    async def fake_create(**kwargs: object) -> SimpleNamespace:
        return response

    agent.openai.chat.completions.create = fake_create
    profile = asyncio.run(agent._extract("Shop", "page text"))
    assert profile.staff[0].name == "Lio"
    assert profile.services[0].name == "Cut"


# ── _load_page (Playwright mocked) ───────────────────────────────────────────


class _FakePage:
    def __init__(self, body: str) -> None:
        self._body = body
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


def test_load_page_truncates_and_closes() -> None:
    agent = _agent()
    page = _FakePage("y" * 20_000)
    browser = _FakeBrowser(page)
    text = asyncio.run(agent._load_page(browser, "https://shop.example/"))  # type: ignore[arg-type]
    assert len(text) == 15_000
    assert browser._ctx.closed is True
    assert page.goto_args == ("https://shop.example/",)


# ── run_once orchestration ───────────────────────────────────────────────────


class _FakePW:
    async def __aenter__(self) -> "_FakePW":
        async def _launch(**kwargs: object) -> MagicMock:
            b = MagicMock()

            async def _close() -> None:
                return None

            b.close = _close
            return b

        self.chromium = SimpleNamespace(launch=_launch)
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def test_run_once_aggregates_stats(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    agent = _agent()
    agent.fetch_targets = lambda limit: [{"id": "1"}, {"id": "2"}]  # type: ignore[method-assign]

    async def fake_enrich(browser: object, shop: dict) -> dict:
        return {"staff": 2, "services": 3, "thin": 0}

    agent.enrich_shop = fake_enrich  # type: ignore[method-assign]
    monkeypatch.setattr(mod, "async_playwright", lambda: _FakePW())

    stats = asyncio.run(agent.run_once(limit=10))
    assert stats == {
        "shops_processed": 2,
        "staff_written": 4,
        "services_written": 6,
        "thin": 0,
    }


def test_run_once_no_targets_short_circuits() -> None:
    agent = _agent()
    agent.fetch_targets = lambda limit: []  # type: ignore[method-assign]
    stats = asyncio.run(agent.run_once())
    assert stats["shops_processed"] == 0


def test_module_run_delegates(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_run_once(limit: int) -> dict:
        return {"shops_processed": 1}

    monkeypatch.setattr(mod.EnrichmentAgent, "run_once", lambda self, limit: fake_run_once(limit))
    assert mod.run(limit=5)["shops_processed"] == 1
