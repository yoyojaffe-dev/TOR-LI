"""Legacy re-classification backfill agent.

A one-off remediation pass. The earliest ``barbershops`` rows were inserted by a
pre-classifier discovery agent that upserted every Google ``places_nearby`` hit
blindly; a later migration then blanket-defaulted their ``place_type`` to
``barber_shop``. So non-barbershops (car rental, clinics, dress shops) wear a
``barber_shop`` label the consumer/agent place_type filters trust wrongly.

This agent re-verifies each unclassified row through the **existing, already
shipped** men's-barbershop classifier (``DiscoveryAgent._is_mens_barbershop``) —
no new AI logic. For each row it:

1. Re-fetches only the Google ``types`` array (cheapest Place Details call) via
   the stored ``google_place_id`` and stores it in ``barbershops.google_types``.
2. Classifies on name + address (from the DB) + the fresh types + any stored
   ``external_reviews`` text. Shops with no stored reviews classify on the
   thinner name/address/types signal — that's not an error, just less context.
3. Demotes non-barbers to ``place_type='non_barber'`` (kept for audit; excluded
   everywhere the existing ``IN ('barber_shop','hair_care')`` filter excludes).

Resumable: ``google_types IS NULL`` is the "not yet processed" marker, set for
every row regardless of outcome, so a restart never re-processes a done row.
"""

import asyncio
import logging
from typing import Any, cast

from app.agents.discovery_agent import _MAX_CONCURRENT_FILTER, DiscoveryAgent

logger = logging.getLogger(__name__)

# place_type sentinel for rows the classifier rejected. Not in the
# ('barber_shop','hair_care') set the consumer RPC + agent queries filter on, so
# these rows are excluded from every customer/agent-facing path automatically.
_NON_BARBER = "non_barber"


class ReclassifyAgent(DiscoveryAgent):
    """Re-verify legacy shops via the inherited men's-barbershop classifier.

    Subclasses ``DiscoveryAgent`` purely to reuse its ``gmaps``/``openai``
    clients, ``supabase_admin`` handle, and ``_is_mens_barbershop`` verbatim.
    The ``discover()`` flow is not used.
    """

    # ------------------------------------------------------------------
    # Reads (sync; called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def fetch_pending(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Real (non-seed, unowned) shops not yet re-classified, oldest first."""
        query = (
            self.db.table("barbershops")
            .select("id, google_place_id, name, address")
            .not_.like("google_place_id", "seed:%")
            .is_("owner_id", "null")
            .is_("google_types", "null")  # resume marker
            .order("created_at", desc=False)
        )
        if limit is not None:
            query = query.limit(limit)
        return cast(list[dict[str, Any]], query.execute().data or [])

    def fetch_reviews_by_shop(self) -> dict[str, list[str]]:
        """Map shop id -> stored external review texts (one query, no N+1)."""
        res = self.db.table("external_reviews").select("barbershop_id, text").execute()
        out: dict[str, list[str]] = {}
        for row in cast(list[dict[str, Any]], res.data or []):
            shop_id, text = row.get("barbershop_id"), row.get("text")
            if shop_id and text:
                out.setdefault(str(shop_id), []).append(str(text))
        return out

    def _fetch_types(self, place_id: str) -> list[str]:
        """Cheapest Place Details call — just the place's ``types`` array."""
        result = self.gmaps.place(place_id, fields=["type"])
        details = cast(dict[str, Any], result.get("result", {}))
        return cast(list[str], details.get("types", []))

    # ------------------------------------------------------------------
    # Write (sync; called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _apply_update(self, shop_id: str, update: dict[str, Any]) -> None:
        self.db.table("barbershops").update(update).eq("id", shop_id).execute()

    # ------------------------------------------------------------------
    # Per-row re-classification (concurrent)
    # ------------------------------------------------------------------

    async def _reclassify_one(
        self, row: dict[str, Any], reviews: dict[str, list[str]], sem: asyncio.Semaphore
    ) -> str:
        """Re-verify one row. Returns 'kept' | 'demoted' | 'error'."""
        shop_id = str(row.get("id"))
        place_id = row.get("google_place_id")
        name = row.get("name") or "Unknown"

        if not place_id:
            logger.warning("No google_place_id for %s (%s) — skipping", name, shop_id)
            return "error"

        try:
            types = await asyncio.to_thread(self._fetch_types, str(place_id))
        except Exception as exc:  # noqa: BLE001 — best-effort; leave row pending for retry
            logger.warning("Types fetch failed for %s (%s): %s", name, shop_id, exc)
            return "error"

        place = {
            "name": name,
            "formatted_address": row.get("address") or "",
            "types": types,
            "reviews": [{"text": t} for t in reviews.get(shop_id, [])],
        }
        async with sem:
            is_mens = await self._is_mens_barbershop(place)

        # google_types is always written so the row is marked processed (won't be
        # re-picked on a resume); place_type only changes for rejected shops.
        update: dict[str, Any] = {"google_types": types}
        if not is_mens:
            update["place_type"] = _NON_BARBER

        try:
            await asyncio.to_thread(self._apply_update, shop_id, update)
        except Exception as exc:  # noqa: BLE001 — best-effort; leave row pending for retry
            logger.error("Update failed for %s (%s): %s", name, shop_id, exc)
            return "error"

        return "kept" if is_mens else "demoted"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, limit: int | None = None) -> dict[str, int]:
        """Re-classify all pending rows. Returns processed/kept/demoted/errors."""
        rows = await asyncio.to_thread(self.fetch_pending, limit)
        reviews = await asyncio.to_thread(self.fetch_reviews_by_shop)
        logger.info("Reclassify pass: %d pending rows", len(rows))
        if not rows:
            return {"processed": 0, "kept": 0, "demoted": 0, "errors": 0}

        sem = asyncio.Semaphore(_MAX_CONCURRENT_FILTER)
        counts = {"kept": 0, "demoted": 0, "error": 0}
        done = 0
        for coro in asyncio.as_completed(
            [self._reclassify_one(row, reviews, sem) for row in rows]
        ):
            counts[await coro] += 1
            done += 1
            if done % 50 == 0:
                logger.info(
                    "… %d/%d done (kept=%d demoted=%d errors=%d)",
                    done,
                    len(rows),
                    counts["kept"],
                    counts["demoted"],
                    counts["error"],
                )

        result = {
            "processed": done,
            "kept": counts["kept"],
            "demoted": counts["demoted"],
            "errors": counts["error"],
        }
        logger.info("Reclassify complete: %s", result)
        return result
