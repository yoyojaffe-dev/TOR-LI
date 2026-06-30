"""Enrichment Agent.

Standalone, batchable pass that fills out barbershop profiles — the team of
barbers and the service menu — by loading each shop's booking page and running
the profile extractor. Decoupled from the scraping loop; triggered on demand for
new / stale records.

Per pass, for each target shop:
1. Load the booking page (headless Playwright); take visible text.
2. Guard: skip pages with too little text (app-walls / redirects) — CONTENT_TOO_THIN.
3. Extract staff + services via OpenAI (gpt-4o-mini, function calling).
4. Guard: keep price/duration only from trusted booking platforms; null them for
   generic/marketing pages.
5. Upsert staff (insert-if-not-exists) then services (resolving barber name -> id);
   never clobbers owner-entered rows.
6. Stamp ``enriched_at`` so the next pass can target stale shops.

Reviews are NOT handled here — the Discovery Agent writes them from Google Places.

Trigger:
    POST /admin/enrichment/run     (one pass, dev only)
    python -m scripts.run_enrichment
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

from openai import AsyncOpenAI
from playwright.async_api import Browser, async_playwright

from app.agents.extraction import (
    PROFILE_EXTRACTION_TOOL,
    build_profile_messages,
    is_content_sufficient,
    is_pricing_source,
    parse_profile,
)
from app.agents.scraping_agent import _is_skippable_url
from app.config import get_settings
from app.models.schemas import ShopEnrichment
from app.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

# Page load + render budget (matches the scraping agent).
_PAGE_TIMEOUT_MS = 20_000
_RENDER_WAIT_MS = 2_500

# Visible-text budget sent to OpenAI — keeps prompt tokens cheap.
_MAX_TEXT_CHARS = 15_000

# Max shops enriched concurrently in one pass.
_MAX_CONCURRENT_SHOPS = 5

# Default shops fetched per pass.
DEFAULT_LIMIT = 50


class EnrichmentAgent:
    """Populates staff + services for barbershops from their booking pages."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = supabase_admin  # service-role: bypasses RLS
        self.openai = AsyncOpenAI(api_key=self.settings.openai_api_key)

    # ------------------------------------------------------------------
    # Supabase (sync, called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def fetch_targets(self, limit: int) -> list[dict[str, Any]]:
        """Shops with a scrapable booking_url, stalest (or never-enriched) first."""
        res = (
            self.db.table("barbershops")
            .select("id, name, booking_url, enriched_at")
            .not_.is_("booking_url", "null")
            # Only enrich actual barbershops — mirrors the place_type restriction
            # the consumer-facing barbershops_within_radius RPC already applies,
            # so non-barbers (car rental, clinics, dress shops) stay out of the
            # enrichment queue instead of polluting staff/services.
            .in_("place_type", ["barber_shop", "hair_care"])
            .order("enriched_at", desc=False, nullsfirst=True)
            .limit(limit)
            .execute()
        )
        return [
            shop for shop in (res.data or []) if not _is_skippable_url(shop.get("booking_url", ""))
        ]

    def _mark_enriched(self, shop_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        self.db.table("barbershops").update({"enriched_at": now}).eq("id", shop_id).execute()

    def _persist(self, shop_id: str, profile: ShopEnrichment) -> tuple[int, int]:
        """Upsert staff then services (resolving barber name -> id). Returns counts."""
        staff_ids: dict[str, str] = {}
        staff_written = 0
        for member in profile.staff:
            try:
                res = self.db.rpc(
                    "upsert_staff", {"p_shop_id": shop_id, "p_name": member.name}
                ).execute()
                sid = res.data if isinstance(res.data, str) else None
                if sid:
                    staff_ids[member.name.strip().lower()] = sid
                staff_written += 1
            except Exception as exc:
                logger.warning("staff upsert failed for %s: %s", shop_id, exc)

        services_written = 0
        for svc in profile.services:
            staff_id = staff_ids.get((svc.staff_name or "").strip().lower())
            try:
                self.db.rpc(
                    "upsert_service",
                    {
                        "p_shop_id": shop_id,
                        "p_name": svc.name,
                        "p_category": svc.category,
                        "p_price": int(svc.price) if svc.price is not None else None,
                        "p_duration_mins": svc.duration_mins,
                        "p_staff_id": staff_id,
                    },
                ).execute()
                services_written += 1
            except Exception as exc:
                logger.warning("service upsert failed for %s: %s", shop_id, exc)

        return staff_written, services_written

    # ------------------------------------------------------------------
    # Playwright + OpenAI
    # ------------------------------------------------------------------

    async def _load_page(self, browser: Browser, url: str) -> str:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            viewport={"width": 390, "height": 844},
            locale="he-IL",
        )
        page = await context.new_page()
        try:
            await page.goto(url, timeout=_PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_timeout(_RENDER_WAIT_MS)
            text = await page.inner_text("body")
            return text[:_MAX_TEXT_CHARS]
        finally:
            await context.close()

    async def _extract(self, shop_name: str, text: str) -> ShopEnrichment:
        response = await self.openai.chat.completions.create(  # type: ignore[call-overload]
            model="gpt-4o-mini",
            messages=build_profile_messages(shop_name, text),
            tools=[PROFILE_EXTRACTION_TOOL],
            tool_choice={"type": "function", "function": {"name": "extract_shop_profile"}},
        )
        tool_call = response.choices[0].message.tool_calls[0]
        args = cast(dict[str, Any], json.loads(tool_call.function.arguments))
        return parse_profile(args)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def enrich_shop(self, browser: Browser, shop: dict[str, Any]) -> dict[str, int]:
        """Enrich one shop. Returns counters for the pass aggregate."""
        shop_id = shop["id"]
        name = shop.get("name", "Unknown")
        url = shop["booking_url"]
        zero = {"staff": 0, "services": 0, "thin": 0}

        try:
            text = await self._load_page(browser, url)

            # Guard 1: skip thin pages (app-walls / redirects) — no OpenAI, no write.
            if not is_content_sufficient(text):
                logger.info("CONTENT_TOO_THIN: %s (%s) — %d chars", name, url, len(text.strip()))
                await asyncio.to_thread(self._mark_enriched, shop_id)
                return {**zero, "thin": 1}

            profile = await self._extract(name, text)

            # Guard 3: trust price/duration only from known booking platforms.
            if not is_pricing_source(url):
                for svc in profile.services:
                    svc.price = None
                    svc.duration_mins = None

            staff_n, services_n = await asyncio.to_thread(self._persist, shop_id, profile)
            await asyncio.to_thread(self._mark_enriched, shop_id)
            logger.info("%s: %d staff, %d services", name, staff_n, services_n)
            return {"staff": staff_n, "services": services_n, "thin": 0}

        except Exception as exc:
            logger.error("Error enriching %s (%s): %s", name, url, exc)
            return zero

    async def run_once(self, limit: int = DEFAULT_LIMIT) -> dict[str, int]:
        """One full pass: fetch targets -> load -> extract -> upsert. Returns stats."""
        targets = await asyncio.to_thread(self.fetch_targets, limit)
        logger.info("Enrichment pass: %d targets", len(targets))

        stats = {"shops_processed": 0, "staff_written": 0, "services_written": 0, "thin": 0}
        if not targets:
            return stats

        sem = asyncio.Semaphore(_MAX_CONCURRENT_SHOPS)

        async def _guarded(shop: dict[str, Any]) -> dict[str, int]:
            async with sem:
                return await self.enrich_shop(browser, shop)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                results = await asyncio.gather(
                    *(_guarded(shop) for shop in targets), return_exceptions=True
                )
            finally:
                await browser.close()

        for result in results:
            stats["shops_processed"] += 1
            if isinstance(result, BaseException):
                logger.error("shop task failed: %s", result)
                continue
            stats["staff_written"] += result["staff"]
            stats["services_written"] += result["services"]
            stats["thin"] += result["thin"]

        return stats


# ---------------------------------------------------------------------------
# Module-level entry points
# ---------------------------------------------------------------------------


async def run_once(limit: int = DEFAULT_LIMIT) -> dict[str, int]:
    return await EnrichmentAgent().run_once(limit)


def run(limit: int = DEFAULT_LIMIT) -> dict[str, int]:
    """Blocking entry point for the standalone script."""
    return asyncio.run(EnrichmentAgent().run_once(limit))
