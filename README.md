# Tor-li (תור־לי)

Real-time, location-based mobile web marketplace for booking **last-minute haircuts**.

A user opens the app, sees haircut slots available **right now** within their GPS
radius (or a city they search), and books in a few taps. Behind the scenes,
autonomous agents discover barbershops from Google Maps, scrape their booking
pages for open slots, and (future) submit the reservation on the barber's own site.

- **Frontend:** Hebrew/RTL, dark-first premium UI (design from Stitch), vanilla JS
  + Tailwind (CDN, no build).
- **Backend:** FastAPI (Python), Supabase (PostgreSQL + PostGIS), pessimistic
  locking done atomically in Postgres (no Redis).
- **Live Supabase project:** `ekugfzrmitvoiamevtfa`.

---

## Stack

| Layer | Tech |
|---|---|
| Backend API | FastAPI, Pydantic v2, Uvicorn |
| DB | Supabase Postgres + PostGIS (geo radius), SECURITY DEFINER RPCs |
| Realtime | Supabase Realtime (`available_slots` table) |
| Agents | Google Maps Places SDK, Playwright (async), OpenAI (function-calling) |
| Frontend (consumer) | Vanilla JS ES modules, Tailwind v3 CDN, Google Maps JS, supabase-js (CDN) |
| Frontend (dashboard) | React via CDN (UMD + htm), buildless |
| Deploy | Railway (`Procfile` + `railway.json`) |

---

## Repository map (every file)

### Root
| Path | Purpose |
|---|---|
| `README.md` | This file. |
| `.gitignore` | Ignores `.env`, `venv`, `*.zip`, caches. |
| `.claude/settings.local.json` | Local Claude Code settings. |

### `backend/` — FastAPI app
| Path | Purpose |
|---|---|
| `requirements.txt` | Python deps (FastAPI, supabase, playwright, openai, googlemaps, twilio, apscheduler, python-multipart…). |
| `Procfile` | Railway/Heroku start: `uvicorn app.main:app`. |
| `railway.json` | Railway build/deploy (Nixpacks, `/health` healthcheck, rootDir=backend). |
| `.env.example` | Documents required env vars (no secrets). |
| `app/main.py` | FastAPI app: CORS, lifespan, router mounting, `/health`. |
| `app/config.py` | `Settings` (pydantic-settings) read from root `.env`; `slot_lock_ttl_seconds=300`. |
| `app/supabase_client.py` | `get_supabase()` (anon key) + `get_supabase_admin()` (service-role, bypasses RLS) + lazy `supabase_admin` proxy. |
| `app/models/schemas.py` | Pydantic models: `Barbershop`, `Slot`, `SlotStatus`, `LockRequest/Response`, `BookingRequest/Response`. |

**Routers** (`app/routers/`)
| Path | Endpoints |
|---|---|
| `barbershops.py` | `GET /barbershops?lat&lng&radius` (PostGIS radius), `GET /barbershops/{id}`. |
| `slots.py` | `GET /slots?barbershop_id&only_free`, `GET /slots/realtime-info`. |
| `bookings.py` | `POST /bookings/lock` (409 if taken), `/release`, `/confirm`; `GET /bookings?user_token` (history). |
| `admin.py` | `POST /admin/discovery/run`, `POST /admin/scraping/run` (manual triggers). |

**Services** (`app/services/`)
| Path | Purpose |
|---|---|
| `locking.py` | Pessimistic lock lifecycle via Postgres RPCs: `acquire_lock`, `release_lock`, `confirm_booking`, `list_bookings`. |

**Agents** (`app/agents/`)
| Path | Purpose |
|---|---|
| `discovery_agent.py` | Google Maps Places → `barbershops` (Nearby + Details, dedup, paginate, upsert via RPC). |
| `scraping_agent.py` | Async Playwright loads booking pages → OpenAI extracts slots → `available_slots` (skips social/auth domains). |
| `booking_agent.py` | **Stub** — will submit the reservation on the barber's site via Playwright. Returns `{success: true}` for now. |

**Scripts** (`backend/scripts/`)
| Path | Purpose |
|---|---|
| `run_discovery.py` | CLI: single-point discovery (`--lat --lng --radius`). |
| `run_national_discovery.py` | CLI: 8-city Israel grid sweep (`--cities --radius --sleep`). |
| `run_scraping.py` | CLI: scraping one pass or `--loop`. |

**Tests** (`backend/tests/`) — 59 tests, external deps mocked
| Path | Covers |
|---|---|
| `test_health.py` | `/health` smoke. |
| `test_discovery_agent.py` | RPC payload, geometry skip, dedup, error isolation. |
| `test_scraping_agent.py` | URL filter, tool schema, slot sync, parse (mocked OpenAI). |
| `test_national_discovery.py` | City-grid selection logic. |
| `test_locking.py` | acquire/release/confirm/list, data-shape edges. |
| `test_routers.py` | Endpoint coverage (TestClient) incl. 409/502/422 paths. |

### `frontend/consumer/` — the live consumer app (vanilla JS)
| Path | Purpose |
|---|---|
| `index.html` | Single-page shell: Stitch dark RTL design + Tailwind config, view containers (`#view-home/barber/success/bookings/profile`), bottom nav. |
| `js/config.js` | Public config: backend URL, Supabase URL + **anon** key, Maps key, lock TTL, default radius. |
| `js/app.js` | **Orchestrator**: hash router, view renderers (home/barber/success/bookings/profile), search, filter sheet, Confirm & Pay sheet, toast. |
| `js/api.js` | Fetch wrappers for the FastAPI endpoints + `ApiError`. |
| `js/state.js` | Tiny observable store + stable per-browser `userToken` (localStorage). |
| `js/geo.js` | GPS (`getCurrentPosition`, null-island guard) + `geocodeAddress` (Google Geocoder). |
| `js/map.js` | Google Maps load, render, `recenterMap`, barbershop markers. |
| `js/booking.js` | Lock → countdown → confirm/cancel lifecycle. |
| `js/realtime.js` | Supabase Realtime subscription to `available_slots`. |
| `js/supabaseClient.js` | supabase-js client init (CDN). |

### `frontend/dashboard/` — barber management dashboard (React CDN, buildless)
| Path | Purpose |
|---|---|
| `index.html` | Dashboard shell (mounts React at `#root`). |
| `js/app.js` | React (UMD + htm) views; subscribes to Realtime. |
| `js/api.js`, `js/config.js` | Same patterns as the consumer app. |

### `frontend/stitch/` — 66 raw Stitch design exports
Reference HTML/CSS frames + design docs (`DESIGN.md`, `MASTER-PROMPT.md`,
`STITCH-HANDOFF.md`). Source of truth for the visual design; not served at runtime.

### `supabase/` — database
| Path | Purpose |
|---|---|
| `config.toml` | Supabase CLI config. |
| `.temp/` | CLI link state (project ref, versions). |
| `migrations/20260625000000_init.sql` | PostGIS, `barbershops`/`available_slots`/`bookings`, radius + lock RPCs, realtime publication. |
| `migrations/…000100_rls_policies.sql` | Public-read RLS + SECURITY DEFINER on write RPCs. |
| `migrations/…000200_grant_anon_select.sql` | Grant anon SELECT + SECURITY DEFINER on radius RPC. |
| `migrations/…000300_upsert_free_slot.sql` | `upsert_free_slot` RPC (never resets a locked/booked slot). |
| `migrations/…20260626000000_persist_bookings.sql` | `bookings.user_token`; `confirm_booking` now inserts the booking row; `bookings_for_user` read RPC. |
| `migrations/…120000_additive_core_tables_users_services_staff.sql` | New `users`, `services`, `staff`; `barbershops.is_active_partner`; FK indexes. Additive — leaves `available_slots`/`bookings` untouched. |
| `migrations/…120100_owner_scoped_writes_and_appointments.sql` | `barbershops.owner_id` + `is_shop_owner()`; owner-scoped write RLS on shops/services/staff/slots; `available_slots.staff_id`; new spec `appointments` table (parallel to `bookings`). |
| `migrations/…120200_harden_is_shop_owner_invoker.sql` | `is_shop_owner` → SECURITY INVOKER + EXECUTE revoked from anon. |
| `migrations/…120300_grant_dml_new_tables.sql` | **Fix:** grant DML on new tables (MCP-created tables got no default grants → RLS was unreachable). |
| `migrations/…120400_grant_owner_dml_existing_tables.sql` | **Fix:** grant authenticated write on `barbershops`/`available_slots` so owner policies can fire. |
| `migrations/…130000_rls_perf_wrap_auth_uid_initplan.sql` | **Perf:** wrap `auth.uid()` as `(select auth.uid())` (per-row → per-query initplan, ~100x on large tables); cache it inside `is_shop_owner`. |

---

## Data model

- **barbershops** — `id, name, address, phone, booking_url, google_place_id,
  location geography(Point,4326), opening_hours jsonb`. GiST index on `location`.
- **available_slots** — `id, barbershop_id, service_name, price, slot_time,
  status (free|locked|booked), locked_until, locked_by`. In the realtime publication.
- **bookings** — `id, slot_id, customer_name, customer_phone, user_token, status`.

### Key RPCs (atomic, in Postgres)
- `barbershops_within_radius(lat,lng,radius_m)` — `ST_DWithin`, nearest-first.
- `lock_slot(slot_id,user,ttl)` — locks if free / lock-expired / **same user**
  (re-entrant); blocks only *other* users.
- `release_slot`, `confirm_booking` (inserts booking + flips slot), `upsert_free_slot`,
  `bookings_for_user`, `upsert_barbershop`.

---

## Identity & multi-tenant schema (auth + owner RLS)

Added on top of the discovery/booking core to give the app real user identity
and shop-owner self-service, secured entirely with Row-Level Security. **Additive
only** — existing tables/RPCs are unchanged, so the running app keeps working.

### New / changed tables
- **users** — profile coupled 1:1 to `auth.users` (`id` FK, `on delete cascade`):
  `role (client|barber|owner), full_name, phone, created_at`. RLS: a user reads/
  updates/inserts **only their own row** (`auth.uid() = id`).
- **services** — per-shop catalog: `id, shop_id→barbershops, name, duration_mins,
  price`. RLS: authenticated read; insert/update/delete only by the shop owner.
- **staff** — per-shop employees: `id, shop_id→barbershops, name, is_active`.
  RLS: authenticated read; owner-only writes.
- **appointments** — spec booking model, **parallel to `bookings`** (not a
  replacement yet): `client_id→users, slot_id→available_slots (unique), status
  (pending|confirmed|completed|cancelled), client_notes, locked_until`. RLS:
  client reads/inserts own; shop owner reads appointments for slots in their shop.
- **barbershops** (existing) — added `is_active_partner` and `owner_id→users`.
  RLS: existing public read kept; owner insert/update added.
- **available_slots** (existing) — added `staff_id→staff`. RLS: existing public
  read kept; owner insert/update/delete added.

### Ownership model
`barbershops.owner_id = auth.uid()` ties a user to their shop. The
`is_shop_owner(shop_id)` predicate (SECURITY INVOKER, authenticated-only EXECUTE)
backs every owner-scoped write policy on services/staff/slots; `barbershops`
checks `owner_id` directly. `service_role` and the existing SECURITY DEFINER RPCs
(Discovery/Scraping agents) bypass RLS and are unaffected.

### Grants — important gotcha
Tables created via the Supabase MCP did **not** inherit Supabase's default
privilege grants. They had only `REFERENCES,TRIGGER,TRUNCATE`, so RLS policies
were dead (PostgREST returns *permission denied* before evaluating RLS) and even
`service_role` could not write. Migrations `…120300` / `…120400` grant the DML
each policy gates. `anon` is intentionally left out (these tables are
authenticated-only).

### Verification
A rolled-back transaction simulated `authenticated` owners/clients (setting
`request.jwt.claims`) and asserted **14 allow/deny cases** — owner can write own
shop's services/staff/slots but not others'; owner can update own shop only;
client can book/see only their own appointment; an unrelated client sees none;
the shop owner can see appointments for their slots. All passed; zero test rows
persisted (re-run after the perf rewrite — still 14/14).

### Performance
All policies follow the Supabase RLS rule: `auth.uid()` is wrapped as
`(select auth.uid())` so it is evaluated once per query (initplan) instead of
once per row, and is cached inside `is_shop_owner`. Every column referenced by a
policy is indexed (`owner_id`, `shop_id`, `client_id`, PKs).

---

## The three agents (coordinate via Supabase)

1. **Discovery** (scheduled) — Google Maps Places → `barbershops`.
   `python -m scripts.run_national_discovery`
2. **Scraping** (continuous) — Playwright + OpenAI → `available_slots`.
   `python -m scripts.run_scraping --loop`
3. **Booking** (on-demand) — submits on the barber's site. **Stub** today.

---

## Booking flow (pessimistic locking)

`tap slot → POST /bookings/lock` (slot → `locked` for 5 min, blocks others) →
**Confirm & Pay** sheet with live countdown → `POST /bookings/confirm`
(Booking Agent submit → slot `booked` + booking row inserted) → **Success** screen
→ **My Bookings**.

---

## Consumer app routes (hash router)

| Route | Screen |
|---|---|
| `#/home` | Discovery: list/map toggle, city search, distance filter |
| `#/barber/:id` | Barber profile: info, call/website, available slots |
| `#/success` | Booking confirmed |
| `#/bookings` | My bookings (real history) |
| `#/profile` | Account (placeholder) |

---

## Setup & run

### Backend
```bash
cd backend
python -m venv ../venv && ../venv/bin/pip install -r requirements.txt
../venv/bin/playwright install chromium          # for the scraping agent
# .env at repo root: SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY,
# GOOGLE_MAPS_API_KEY, OPENAI_API_KEY, (TWILIO_*)… — see backend/.env.example
../venv/bin/uvicorn app.main:app --reload        # http://localhost:8000  (/docs)
```

### Frontend
```bash
cd frontend/consumer
python3 -m http.server 5500                       # http://localhost:5500
```
Mobile-first (430px). Deny GPS → falls back to Jerusalem; search a city to browse
elsewhere. Only seeded shops have bookable slots (scraper isn't populating live).

### Tests
```bash
cd backend && ../venv/bin/python -m pytest -q     # 59 passed
```

---

## Environment / secrets

`.env` (repo root, **gitignored**) holds live Supabase / Google Maps / OpenAI /
Twilio secrets. The Supabase **anon** key is public (shipped in frontend config).
The **service-role** key is backend-agents-only (bypasses RLS) — never in frontend.

---

## Branches

| Branch | Contents |
|---|---|
| `main` | Agents + frontend + tests (pre booking-sheet UI). |
| `Develope` | Full current app (everything documented here). |
| `feature/booking-sheet` | Booking sheet, router, profile/success/my-bookings, bookings persistence. |
| `sms-confirmation` | **Parked, local-only** — WIP Twilio SMS reminder bot, not merged. |

---

## Known gaps / next

- **Booking Agent** is a stub (no real Playwright submission yet).
- **Scraping** doesn't populate live shops (most use external booking platforms);
  only `Test Cuts E2E` has seeded slots.
- **Profile** tab is a placeholder; **cancel booking** flow not built.
- `opening_hours` not persisted (service-role lacks `UPDATE` grant on `barbershops`).
- Tailwind tokens are duplicated across HTML files (planned: one shared token file).
- Auth/onboarding screens (splash, role, SMS) are designed in Stitch, not built.
