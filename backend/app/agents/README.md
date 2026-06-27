# Tor-li Agents

Three autonomous agents build and maintain the booking data. They are **decoupled** —
they share state only through Supabase (Postgres), never in-process. The API serves the
same tables the agents write.

| Agent | File | Job | Status |
|---|---|---|---|
| **Discovery** | `discovery_agent.py` | Find men's barbershops on Google Maps, AI-filter, upsert | Live |
| **Scraping** | `scraping_agent.py` | Load each shop's booking page, extract open slots via OpenAI | Live |
| **Booking** | `booking_agent.py` | Submit a reservation on the barber's site (Playwright + AI) | Live |
| **Enrichment** | `enrichment_agent.py` | Fill profiles: staff + per-barber services from booking pages | Live |

All agents use the **service-role** Supabase client (`supabase_admin`, bypasses RLS) and
write via SECURITY DEFINER RPCs — never raw table inserts.

### Pipeline

```
Discovery ─upsert─▶ barbershops ─read─▶ Scraping ─upsert─▶ available_slots
                                                                  │ read
                                                                  ▼
                              user: lock ─▶ Booking (submit on site) ─▶ confirm ─▶ booked
```

Discovery + Scraping are batch/loop workers; Booking is on-demand
(`POST /bookings/confirm`). They never call each other — every handoff is a Supabase row.

---

## Discovery Agent

Two-stage async pipeline that populates the `barbershops` table with **men's barbershops only**.

```
Google Places ──fetch──▶ candidates ──AI filter (concurrent)──▶ men's? ──▶ upsert_barbershop RPC
   (sync SDK)                              gpt-4o-mini             skip if not
```

### Stage 1 — Fetch (`_fetch_candidates`)
- Uses the sync `googlemaps` SDK (nearby search + Place Details), run off the event loop
  via `asyncio.to_thread`. Pagination via `next_page_token` (the SDK's required 2s delay
  is preserved).
- Searches both `barber_shop` and `hair_care` place types and dedups by `place_id`.
- Detail fields include `reviews` and `types` to feed the classifier.
  > **Cost:** `reviews` is a billed Google "Atmosphere" SKU.

### Stage 2 — Filter + upsert (`_verify_and_upsert`)
- Each candidate is classified concurrently (`asyncio.gather` + `Semaphore(5)`).
- Classification calls OpenAI **`gpt-4o-mini`** with forced function calling
  (`MENS_FILTER_TOOL` → `classify_barbershop`) returning a strict boolean
  `is_mens_barbershop`. Reviews may be Hebrew.
- **Fails closed:** any OpenAI error → treated as *not* men's → skipped.
- Non-men's shops are **skipped** (never written). Confirmed shops upsert via the
  `upsert_barbershop` RPC; `opening_hours` is patched in a follow-up update.
  > **Cost:** one `gpt-4o-mini` call per candidate.

### Run it (from `backend/`)

```bash
# Single point
../venv/bin/python -m scripts.run_discovery --lat 32.0853 --lng 34.7818 --radius 5000

# Nationwide grid (10 cities, sequential, rate-limit-safe)
../venv/bin/python -m scripts.run_national_discovery                       # full sweep, 15km
../venv/bin/python -m scripts.run_national_discovery --cities tiberias --radius 3000  # cheap smoke
../venv/bin/python -m scripts.run_national_discovery --radius 20000 --sleep 5

# Dev-only HTTP trigger (admin router mounts when ENVIRONMENT != production)
curl -X POST "http://localhost:8000/admin/discovery/run?lat=32.0853&lng=34.7818&radius_m=5000"
```

> These hit live Google / OpenAI / Supabase and **cost money**. Scope test runs with
> `--cities` / `--radius`.

### Nationwide grid

`scripts/run_national_discovery.py` sweeps 10 Israeli population centres, north→south,
one at a time with an `asyncio.sleep` gap between cities (Google rate-limit safe).
Concurrency lives *inside* each city's AI-filter stage.

| | |
|---|---|
| Cities | Kiryat Shmona, Tiberias, Haifa, Netanya, Tel Aviv, Rishon LeZion, Jerusalem, Ashdod, Beer Sheva, Eilat |
| Default radius | 15 km (`--radius` to override) |
| Gap between cities | 3 s (`--sleep` to override) |
| Subset | `--cities haifa,eilat` (lowercase keys) |

---

## Booking Agent

On-demand worker behind `POST /bookings/confirm`. After the slot is locked, it loads the
barber's booking page and **routes to a platform adapter** to submit the reservation.

```
fetch slot+shop ─▶ goto(booking_url) ─▶ get_adapter(url) ─▶ adapter.submit() ─▶ [submit] ─▶ verify
```

1. `_fetch_slot_context(slot_id)` — joins the slot to its barbershop `booking_url` / `name`
   (sync, via `asyncio.to_thread`). Rejects missing/unsupported URLs (`_is_skippable_url`).
2. Headless Chromium (mobile UA, `he-IL`) loads the page.
3. `get_adapter(url)` picks the adapter by platform; the adapter fills the form and — **if
   `BOOKING_LIVE=true` — clicks submit and verifies a confirmation keyword**. Default is dry
   run (fill, no click). Returns `{"success": bool, ...}` — on failure the router releases the
   lock and returns HTTP 502.

> ⚠️ **A live submit books a real appointment** (irreversible). `BOOKING_LIVE` defaults to
> `false` (dry run). Flip it to `true` only against booking sites you're authorized to submit to.

### Platform adapters (`booking_adapters/`)

Real shops run a handful of known platforms whose DOM is stable — scripting them directly is
faster, cheaper, and more reliable than asking the model every time. `detect_platform(url)`
maps the booking URL to a platform; `get_adapter(url, openai)` returns the matching adapter,
or the AI fallback for unknown sites.

| Adapter | Platform | How it maps the form |
|---|---|---|
| `Tor4YouAdapter` | `tor4you` | static selectors (boilerplate — TODO: verify real DOM) |
| `GlameraAdapter` | `glamera` | static selectors (boilerplate — TODO: verify real DOM) |
| `GenericAIAdapter` | `custom` (fallback) | `gpt-4o-mini` `fill_booking_form` function calling |

Booksy and any unrecognised host currently route to the AI fallback. All adapters share
`base.fill_and_submit`, which honours `BOOKING_LIVE`. The detected platform is stored on
`barbershops.booking_platform` at discovery time.

**Validate routing without real shops** (real Chromium, local fixtures):

```bash
BOOKING_LIVE=true ../venv/bin/python -m scripts.validate_booking
```

Serves `tests/fixtures/booking/{tor4you,glamera,custom}.html` under real platform hostnames
(via Playwright request interception) and asserts each routes to the right adapter, fills,
submits, and detects confirmation.

---

## Orchestration

The three agents run together two ways:

**Pipeline script** — `scripts/run_agents.py`: one Discovery pass → continuous Scraping loop.

```bash
../venv/bin/python -m scripts.run_agents --lat 32.7922 --lng 35.5312 --radius 3000
../venv/bin/python -m scripts.run_agents --national --cities haifa,eilat   # grid, then scrape loop
../venv/bin/python -m scripts.run_agents --no-scrape                       # discovery only
```

**Lifespan auto-start** — `main.py` launches the Scraping loop on boot **only when
`AGENTS_AUTOSTART=true`** (off by default — agents bill continuously, including prod).
Booking stays on-demand.

---

## Enrichment Agent

Standalone, batchable pass (`enrichment_agent.py`) that fills out profiles — the **team of
barbers** and the **service menu** — by loading each shop's booking page and running the profile
extractor. Decoupled from the scraping loop; run it for new/stale records.

```
fetch stalest shops ─▶ load page ─▶ [guard: thin?] ─▶ extract (gpt-4o-mini) ─▶ [guard: pricing?] ─▶ upsert staff+services
```

- `fetch_targets` — shops with a scrapable `booking_url`, `enriched_at nulls first` (stale first).
- **Guard 1 — min content:** pages under `MIN_CONTENT_LENGTH` (200 chars; app-walls/redirects) are
  logged `CONTENT_TOO_THIN`, stamped `enriched_at`, and skipped — no OpenAI, no write.
- **Guard 2 — hard-negative prompt:** the model must omit any staff/service not on the page (but it
  *does* classify listed services into a category — inference, not invention).
- **Guard 3 — platform-priority pricing:** price/duration kept only from trusted booking platforms
  (`is_pricing_source`: tor4you/glamera); nulled for generic/marketing pages.
- Upserts via `upsert_staff` / `upsert_service` (insert-if-not-exists; resolves barber name→id;
  never clobbers owner rows). `ON CONFLICT DO NOTHING` → **first write wins** (re-enrichment does
  not backfill existing rows — a future "refresh" mode).
- **Reviews are NOT here** — Discovery writes them from Google Places (`upsert_external_review`),
  filtered by `filter_reviews` (drops anonymous/empty).

Run it (from `backend/`):
```bash
../venv/bin/python -m scripts.run_enrichment --limit 4        # billed: live pages + OpenAI + writes
curl -X POST "http://localhost:8000/admin/enrichment/run?limit=10"   # dev-only
```

> **Best-effort coverage** (validated on live shops): app-walled widgets (smartor) and dead domains
> are skipped/error-isolated; marketing sites yield service **names + categories** but no
> price/duration; per-barber mapping is rare from public pages.

---

## Profile extraction layer

The schema + extraction primitives behind the Enrichment Agent. The runtime above is now wired;
this section documents the building blocks.

**Schema** (migration `20260627100000_full_profile_extraction.sql`):
- `external_reviews` — scraped/aggregated reviews (`barbershop_id`, `author`, `rating`, `text`,
  `source`, `reviewed_at`). Separate from the in-app `reviews` table (which is keyed to a
  `booking_id` + `user_token`). Public-read RLS; agents write via service-role.
- `services.staff_id` (FK → `staff`, nullable) + `services.category` — services map **per barber**
  (`staff_id` null = a shop-level general service).
- Portfolio unchanged: `barbershops.photo_urls` (barbers upload real portfolios via the dashboard).

**Extraction layer** (`app/agents/extraction.py`, no I/O — unit-tested in isolation):
- `PROFILE_EXTRACTION_TOOL` + `build_profile_messages(shop_name, page_text)` — OpenAI
  function-calling schema + prompt to pull staff/services/reviews from booking-page text.
- `parse_profile(tool_args) -> ShopEnrichment` — validates the tool call into Pydantic models
  (`ExtractedStaff`, `ExtractedService`, `ExternalReview` in `models/schemas.py`).
- `external_reviews_from_place(place)` — maps Google Places `reviews[]` (already structured, no LLM).

- Guards: `is_content_sufficient`, `is_pricing_source`, `filter_reviews` (all pure, unit-tested).

> **Best-effort, partial coverage.** Google Places exposes none of staff / per-barber menus /
> durations — those come only from booking pages, and many shops have no booking_url. The models
> leave absent fields `None`; nothing assumes a complete profile.

---

## Config (`.env` at repo root)

| Var | Used by |
|---|---|
| `GOOGLE_MAPS_API_KEY` | Discovery (Places) |
| `OPENAI_API_KEY` | Discovery (filter), Scraping (slots), Booking (form mapping) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | All agents (service-role writes) |
| `BOOKING_LIVE` | Booking — `true` submits for real; default `false` = dry run (fill, no submit). |
| `AGENTS_AUTOSTART` | `main.py` — `true` starts the Scraping loop on boot. Default `false`. |

## Tests

```bash
../venv/bin/python -m pytest tests/test_discovery_agent.py tests/test_scraping_agent.py \
  tests/test_booking_agent.py tests/test_national_discovery.py tests/test_pipeline_e2e.py -q
```

Google Maps, OpenAI, Playwright, and Supabase are all mocked — no network. `test_pipeline_e2e.py`
threads all three agents through one stateful fake DB (free→locked→booked). Async paths are
exercised via `asyncio.run(...)` in sync test functions; coverage gate is 90%.
