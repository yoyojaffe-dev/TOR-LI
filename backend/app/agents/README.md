# Tor-li Agents

Three autonomous agents build and maintain the booking data. They are **decoupled** —
they share state only through Supabase (Postgres), never in-process. The API serves the
same tables the agents write.

| Agent | File | Job | Status |
|---|---|---|---|
| **Discovery** | `discovery_agent.py` | Find men's barbershops on Google Maps, AI-filter, upsert | Live |
| **Scraping** | `scraping_agent.py` | Load each shop's booking page, extract open slots via OpenAI | Live |
| **Booking** | `booking_agent.py` | Submit a reservation on the barber's site (Playwright + AI) | Live |

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

On-demand worker behind `POST /bookings/confirm`. After the slot is locked, it submits the
reservation on the barber's own site.

```
fetch slot+shop ─▶ goto(booking_url) ─▶ AI maps form ─▶ fill fields ─▶ [submit] ─▶ verify
```

1. `_fetch_slot_context(slot_id)` — joins the slot to its barbershop `booking_url` / `name`
   (sync, via `asyncio.to_thread`). Rejects missing/unsupported URLs (`_is_skippable_url`).
2. Headless Chromium (mobile UA, `he-IL`) loads the page; grabs the form HTML.
3. `gpt-4o-mini` function calling (`fill_booking_form` → `fields` + `submit_selector` +
   `confirmation_keywords`) maps the customer's name/phone onto the page's selectors.
4. Fills the fields. **If `BOOKING_LIVE` (default true): clicks submit and verifies a
   confirmation keyword.** Returns the `{"success": bool, ...}` contract — on failure the
   router releases the lock and returns HTTP 502.

> ⚠️ **A live submit books a real appointment.** Set `BOOKING_LIVE=false` to fill the form
> but skip the final click (dry run) — use this whenever testing against real sites.

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

## Config (`.env` at repo root)

| Var | Used by |
|---|---|
| `GOOGLE_MAPS_API_KEY` | Discovery (Places) |
| `OPENAI_API_KEY` | Discovery (filter), Scraping (slots), Booking (form mapping) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | All agents (service-role writes) |
| `BOOKING_LIVE` | Booking — `false` = dry run (fill, no submit). Default `true`. |
| `AGENTS_AUTOSTART` | `main.py` — `true` starts the Scraping loop on boot. Default `false`. |

## Tests

```bash
../venv/bin/python -m pytest tests/test_discovery_agent.py tests/test_scraping_agent.py \
  tests/test_booking_agent.py tests/test_national_discovery.py tests/test_pipeline_e2e.py -q
```

Google Maps, OpenAI, Playwright, and Supabase are all mocked — no network. `test_pipeline_e2e.py`
threads all three agents through one stateful fake DB (free→locked→booked). Async paths are
exercised via `asyncio.run(...)` in sync test functions; coverage gate is 90%.
