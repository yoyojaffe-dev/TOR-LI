# Tor-li (תור־לי)

Real-time, location-based web app for booking **last-minute men's haircuts**. A user opens the
app, sees free slots near their GPS / searched location, and books in a few taps. Behind the
scenes, autonomous agents discover barbershops from Google Maps, scrape booking pages for open
slots, enrich shop profiles (team + service menu), and submit the reservation on the barber's own
site. Hebrew/RTL frontend.

- **Backend:** FastAPI (Python), async agents.
- **Database:** Supabase (PostgreSQL + PostGIS), pessimistic locking in atomic SQL RPCs.
- **Frontend:** buildless vanilla JS ES modules + Tailwind (CDN).
- **Live Supabase project:** `ekugfzrmitvoiamevtfa`.

> **Status:** Foundation phase complete — the four-agent data pipeline and full barbershop-profile
> schema are live on `main`. Frontend phase next.

---

## Architecture — the four-agent "message board"

The agents are **decoupled**: they share state only through Supabase (Postgres), never in-process.
The API serves the same tables the agents write. Each handoff is a row.

```
Discovery ──▶ barbershops ──▶ Scraping ──▶ available_slots ──▶ booking flow ──▶ Booking
   (Google Places          (booking pages          (lock → confirm)        (submit on
    + AI men's filter)       → open slots)                                  barber's site)
       │                                                                        ▲
       └──▶ external_reviews        Enrichment ──▶ staff + services ───────────┘
            (Google reviews)        (booking pages → team + menu)
```

| Agent | Role | Source | Trigger |
|---|---|---|---|
| **Discovery** | Find men's barbershops; AI-filter; store shop + Google reviews | Google Places | script / `POST /admin/discovery/run` |
| **Scraping** | Extract open appointment slots | booking pages (Playwright + OpenAI) | loop / `POST /admin/scraping/run` |
| **Enrichment** | Fill profiles: team + per-barber service menu (guarded) | booking pages (Playwright + OpenAI) | `run_enrichment` / `POST /admin/enrichment/run` |
| **Booking** | Submit a reservation; platform adapters + AI fallback | barber's booking site | `POST /bookings/confirm` |

---

## Repository structure

```
/
├── backend/            # FastAPI app + async agents
│   ├── app/
│   │   ├── agents/         # the four agents + extraction + booking adapters
│   │   ├── routers/        # HTTP API endpoints
│   │   ├── services/       # locking (pessimistic slot locks via RPCs)
│   │   ├── models/         # Pydantic v2 request/response + extraction models
│   │   ├── config.py       # settings from repo-root .env
│   │   └── main.py         # FastAPI entrypoint + lifespan (optional agent autostart)
│   ├── scripts/        # CLI runners for the agents
│   ├── tests/          # pytest suite (mocked — no network)
│   └── pyproject.toml  # mypy/ruff/black/coverage config
├── supabase/
│   └── migrations/     # SQL schema + SECURITY DEFINER RPCs (applied to the live project)
├── frontend/           # buildless consumer app + barber dashboard (Frontend phase)
└── specs/              # reverse-engineered spec
```

### `/backend/app/agents/` — core agent logic
- `discovery_agent.py` — Google Places search → AI men's-barbershop classifier (`gpt-4o-mini`,
  function calling) → upsert; also writes filtered Google reviews to `external_reviews`.
- `scraping_agent.py` — headless Playwright → OpenAI slot extraction → `upsert_free_slot`.
- `enrichment_agent.py` — loads booking pages → extracts **staff + per-barber services** with four
  guards (min-content gate, hard-negative prompt, platform-priority pricing, anonymous-review
  filter); upserts via `upsert_staff` / `upsert_service`.
- `extraction.py` — runtime-agnostic profile-extraction primitives (tool schema, prompt builder,
  parsers) + the guards (`is_content_sufficient`, `is_pricing_source`, `filter_reviews`).
- `booking_agent.py` + `booking_adapters/` — detect the booking platform and route to a dedicated
  adapter (Tor4You, Glamera) or the generic AI fallback; `BOOKING_LIVE` gates real submits.
- See `backend/app/agents/README.md` for the deep dive.

### `/backend/app/routers/` — API endpoints
- `barbershops.py` — shop search + PostGIS radius. `slots.py` — slot lists / nearby.
- `bookings.py` — lock → confirm → cancel flow. `reviews.py` — in-app reviews.
- `admin.py` — dev-only ops triggers (mounted when `ENVIRONMENT != production`):
  `/admin/discovery/run`, `/admin/scraping/run`, **`/admin/enrichment/run`**.

### `/backend/scripts/` — CLI runners
- `run_discovery.py` / `run_national_discovery.py` — single-point / 10-city grid discovery.
- `run_scraping.py` — one pass or continuous slot-scraping loop.
- **`run_enrichment.py`** — enrichment pass (`--limit`), stalest shops first.
- `run_agents.py` — pipeline orchestrator (discovery → scraping loop).
- `validate_booking.py` — real-browser booking-adapter routing harness (local fixtures).
- `_cli.py` — shared argparse validators + SIGINT-safe entrypoint.

### `/backend/tests/` — unit tests (~94% branch coverage)
All external services (Supabase, OpenAI, Google, Playwright) are mocked — **no network**. Includes
a mocked end-to-end pipeline test (`test_pipeline_e2e.py`) and per-agent suites. Coverage gate
`fail_under=90` enforced in `pyproject.toml`.

### `/supabase/migrations/` — schema + RPCs
SQL migrations applied to the live project (via the Supabase CLI / MCP). Covers the full profile
schema: `barbershops`, `available_slots`, `bookings`, `reviews`, `external_reviews`, `staff`,
`services` (per-barber via `staff_id`), `users`/`appointments`, plus SECURITY DEFINER RPCs
(`upsert_barbershop`, `upsert_free_slot`, `lock_slot`/`confirm_booking`, `upsert_staff`,
`upsert_service`, `upsert_external_review`, radius/nearby search). Public-read RLS on shop-facing
tables; owner-scoped writes; service-role for agents.

---

## Commands (from `backend/`)

```bash
# API
../venv/bin/uvicorn app.main:app --port 8000

# Tests + quality gates
../venv/bin/python -m pytest tests/ -q --cov=app --cov-report=term-missing   # gate: 90%
../venv/bin/python -m mypy --strict
../venv/bin/ruff check app tests scripts && ../venv/bin/black app tests scripts

# Agents (billed — hit live Google / OpenAI / Supabase)
../venv/bin/python -m scripts.run_national_discovery --cities tiberias --radius 3000
../venv/bin/python -m scripts.run_scraping --loop --interval 120
../venv/bin/python -m scripts.run_enrichment --limit 10
```

## Configuration (`.env` at repo root)

| Var | Used by |
|---|---|
| `SUPABASE_URL`, `SUPABASE_KEY` | API (anon, RLS-enforced) |
| `SUPABASE_SERVICE_ROLE_KEY` | Agents (bypass RLS) |
| `GOOGLE_MAPS_API_KEY` | Discovery |
| `OPENAI_API_KEY` | Discovery / Scraping / Enrichment / Booking |
| `BOOKING_LIVE` | Booking — `true` submits for real; default `false` (dry run) |
| `AGENTS_AUTOSTART` | `main.py` — `true` starts the Scraping loop on boot; default `false` |

## Known limitations (best-effort by design)
- Google Places exposes no staff / per-barber menus / durations; those come only from booking
  pages, many of which are app-walled or absent — coverage is partial, absent fields stay `null`.
- `upsert_service` is `ON CONFLICT DO NOTHING` (first-write-wins) — re-enrichment doesn't backfill
  existing rows yet.
- Real per-barber prices require logged-in booking-widget integration (future).
