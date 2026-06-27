"""Mocked end-to-end pipeline test.

Threads the three-agent "message board" through a single stateful fake DB, with
no network: Discovery upserts a shop -> Scraping writes a free slot for it ->
the booking flow locks the slot -> the Booking Agent submits -> confirm flips it
to booked. Proves the agents hand off purely through shared DB state and that
the slot state machine (free -> locked -> booked) holds end to end.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agents.booking_agent import BookingAgent
from app.agents.discovery_agent import DiscoveryAgent
from app.agents.scraping_agent import ScrapingAgent
from app.services import locking


class FakeDB:
    """Minimal stateful Supabase double modelling shops + slots + the RPCs."""

    def __init__(self) -> None:
        self.shops: dict[str, dict] = {}
        self.slots: dict[str, dict] = {}
        self._shop_seq = 0
        self._slot_seq = 0

    # -- RPC dispatch (agents + locking go through here) --
    def rpc(self, name: str, args: dict) -> "FakeDB._Exec":
        handler = getattr(self, f"_rpc_{name}")
        return FakeDB._Exec(handler(args))

    def _rpc_upsert_barbershop(self, args: dict) -> list:
        self._shop_seq += 1
        shop_id = f"shop-{self._shop_seq}"
        self.shops[shop_id] = {
            "id": shop_id,
            "name": args["p_name"],
            "booking_url": args.get("p_booking_url"),
        }
        return [{"upsert_barbershop": shop_id}]

    def _rpc_upsert_free_slot(self, args: dict) -> list:
        self._slot_seq += 1
        slot_id = f"slot-{self._slot_seq}"
        self.slots[slot_id] = {
            "id": slot_id,
            "barbershop_id": args["p_barbershop_id"],
            "service_name": args["p_service_name"],
            "slot_time": args["p_slot_time"],
            "status": "free",
            "locked_by": None,
        }
        return [{"upsert_free_slot": slot_id}]

    def _rpc_lock_slot(self, args: dict) -> list:
        slot = self.slots[args["p_slot_id"]]
        if slot["status"] != "free":
            return [{"success": False, "message": "already locked or booked"}]
        slot["status"] = "locked"
        slot["locked_by"] = args["p_user"]
        return [{"success": True, "locked_until": "2026-06-27T12:05:00+03:00", "message": "locked"}]

    def _rpc_confirm_booking(self, args: dict) -> list:
        slot = self.slots[args["p_slot_id"]]
        if slot["status"] != "locked" or slot["locked_by"] != args["p_user"]:
            return [{"success": False, "status": "failed", "message": "lock not held"}]
        slot["status"] = "booked"
        return [{"success": True, "status": "booked", "message": "confirmed"}]

    # -- table() select used by Booking Agent's _fetch_slot_context --
    def table(self, name: str) -> "FakeDB._Table":
        return FakeDB._Table(self)

    class _Exec:
        def __init__(self, data: list) -> None:
            self._data = data

        def execute(self) -> SimpleNamespace:
            return SimpleNamespace(data=self._data)

    class _Table:
        def __init__(self, db: "FakeDB") -> None:
            self._db = db
            self._id: str | None = None

        def select(self, *a: object, **k: object) -> "FakeDB._Table":
            return self

        def eq(self, col: str, val: str) -> "FakeDB._Table":
            self._id = val
            return self

        def limit(self, n: int) -> "FakeDB._Table":
            return self

        def execute(self) -> SimpleNamespace:
            slot = dict(self._db.slots[self._id]) if self._id in self._db.slots else {}
            if slot:
                shop = self._db.shops[slot["barbershop_id"]]
                slot["barbershops"] = {"name": shop["name"], "booking_url": shop["booking_url"]}
            return SimpleNamespace(data=[slot] if slot else [])


def _discovery(db: FakeDB) -> DiscoveryAgent:
    a = DiscoveryAgent.__new__(DiscoveryAgent)
    a.settings = SimpleNamespace(google_maps_api_key="test")
    a.db = db
    return a


def _scraping(db: FakeDB) -> ScrapingAgent:
    a = ScrapingAgent.__new__(ScrapingAgent)
    a.settings = SimpleNamespace(openai_api_key="test")
    a.db = db
    return a


def _booking(db: FakeDB) -> BookingAgent:
    a = BookingAgent.__new__(BookingAgent)
    a.settings = SimpleNamespace(booking_live=True, openai_api_key="test")
    a.db = db
    return a


def test_pipeline_discovery_to_booked(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    db = FakeDB()
    user = "user-token-1"

    # 1. Discovery upserts a men's barbershop (with its booking_url).
    _discovery(db)._upsert(
        {
            "place_id": "PID1",
            "name": "Cool Cuts",
            "website": "https://book.coolcuts.example",
            "geometry": {"location": {"lat": 32.1, "lng": 34.8}},
        }
    )
    assert len(db.shops) == 1
    shop_id = next(iter(db.shops))

    # 2. Scraping writes a free slot for that shop.
    written = _scraping(db)._sync_slots(
        shop_id,
        [{"service_name": "Men's Cut", "slot_time": "2026-06-28T10:00:00+03:00", "price": 60}],
    )
    assert written == 1
    slot_id = next(iter(db.slots))
    assert db.slots[slot_id]["status"] == "free"

    # 3. A booker locks the slot (anon client -> same fake DB).
    monkeypatch.setattr(locking, "get_supabase", lambda: db)
    lock = locking.acquire_lock(slot_id, user)
    assert lock.success is True
    assert db.slots[slot_id]["status"] == "locked"

    # 4. Booking Agent submits on the discovered booking_url (browser/AI mocked).
    agent = _booking(db)
    used_url: dict[str, str] = {}

    async def fake_book(browser, url, sid, name, phone, slot_time):  # type: ignore[no-untyped-def]
        used_url["url"] = url
        return {"success": True, "slot_id": sid, "confirmed": True}

    agent._book_on_page = fake_book  # type: ignore[method-assign]

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

    monkeypatch.setattr("app.agents.booking_agent._is_skippable_url", lambda url: False)
    monkeypatch.setattr("app.agents.booking_agent.async_playwright", lambda: _PW())

    result = asyncio.run(agent.submit(slot_id, "Dana", "+972500000000"))
    assert result["success"] is True
    # The URL Discovery wrote flowed all the way to the Booking Agent.
    assert used_url["url"] == "https://book.coolcuts.example"

    # 5. Confirm the booking -> slot becomes booked.
    booking = locking.confirm_booking(slot_id, user, "bk-1", "Dana", "+972500000000")
    assert booking.success is True
    assert booking.status == "booked"
    assert db.slots[slot_id]["status"] == "booked"
