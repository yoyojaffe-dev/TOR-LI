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

> **Status — MVP complete** (branch `feature/barber-dashboard-mvp`). Foundation (four-agent
> pipeline + full profile schema) is live on `main`; the **Consumer app** (phases 1–5.1) and the
> **Barber Dashboard** (phase 6 + advanced statistics, active/inactive toggles, hardened settings)
> are built and browser-verified. A unified landing routes to either app. Next features:
> see [`docs/future_growth_roadmap.md`](docs/future_growth_roadmap.md).
>
> **In progress — Authentication layer** (branch `feature/auth-layer`, *pending live verification*).
> Client **phone SMS-OTP** login (Supabase-native, Twilio configured in the Supabase dashboard) and
> a unified **GoTrue session** model: the consumer's old anonymous `user_token` is replaced by a
> real JWT, and the booking/review RPCs are scoped by `auth.uid()`. See [Authentication](#authentication).
> ⚠️ Not yet merged — the RPC change is breaking and must ship in lockstep with its migrations.

## Key features

**Consumer app** — GPS/search-based shop discovery, viewport-driven map (pan → "search this area"),
barbershop profiles (services / live slots / portfolio / reviews), registration + profile (avatar to
Supabase Storage), **end-to-end booking** (pessimistic lock → countdown → confirm → DB), favorites,
mock payments, capped home carousels with full-list pages, and cascading filters.

**Barber Dashboard** — Supabase-Auth login/registration + 5-step onboarding (business → services →
staff → payment → sync); **5-tab management**: Calendar (live appointments with client name/phone +
slot management), **Statistics** (per-employee + time-period filters, dynamic charts), Employees,
Services, Settings.

**Cross-cutting** — **RLS security** (owner-scoped policies + `SECURITY DEFINER` booking RPCs;
`owner_read_bookings` lets an owner read only their shop's bookings); **active/inactive toggles** on
staff + services that **globally** hide deactivated items from the consumer + operational pickers
while keeping them in the management view; **hardened settings** (confirmation modals on every
destructive action + re-authentication for password changes); live Supabase Realtime everywhere.

## Quick start (run it)

```bash
# 1) Backend API (data + booking + dev barber signup)
cd backend && ../venv/bin/uvicorn app.main:app --port 8000

# 2) Unified frontend — landing + consumer + dashboard from one origin
cd frontend && python3 -m http.server 4000
```
Open **http://localhost:4000/** → choose **הזמנת תספורת** (consumer, `/consumer/`) or **ניהול מספרה**
(dashboard, `/dashboard/`). Demo barber: **`barber@torli.dev` / `torli1234`** (owns a seeded shop with
a real appointment). Seed/refresh mock data with the scripts in `scripts/` (see below).

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

## Consumer Frontend (Phases 1–5.1)

A **buildless** single-page app in `frontend/consumer/` — vanilla JS ES modules + Tailwind (CDN),
no bundler, no `package.json`. Hash-router SPA, Hebrew/RTL, dark theme with gold accent. The UI
targets the **Stitch** design mockups in `frontend/stitch/` (the shared design system: `#131315`
background, `#efb200`/`#ffd174` gold, `surface-*` tiers, `rounded-[20px]` cards, floating-label
inputs, glassmorphic bottom sheets).

### Architecture — user identity
Clients log in with **phone SMS-OTP** (Supabase Auth / GoTrue) — see [Authentication](#authentication).
A verified session (access + refresh JWT) is held in `localStorage` under `torli_session` and sent as
`Authorization: Bearer …` on every booking/review call; the backend RPCs scope by `auth.uid()`.
Booking, cancelling, and reviewing require a session (the RTL OTP modal pops on first booking). A
separate `torli_device_id` (`crypto.randomUUID()`) is kept only for non-auth keys like avatar
filenames, so uploads work before login. The app reads data two ways:
- **FastAPI backend** (`js/api.js`) — barbershops, slots, lock→confirm booking, in-app reviews, and
  the `/auth/*` OTP endpoints.
- **Direct Supabase anon client** (`js/supabaseClient.js`) — public-read tables (`services`,
  `staff`, `external_reviews`) and Storage uploads. RLS enforces anon read-only.

**Client state lives in `localStorage`** (per browser): `torli_session` (GoTrue JWTs),
`torli_device_id`, `torli_onboarded`, `torli_customer_name`/`_phone`, `torli_avatar` (Supabase
Storage URL), `torli_favorites` (shop-id array), `torli_pay_method` / `torli_pay_cards` (masked). A
tiny observable store (`js/state.js`) holds in-memory state (position, fetched shops/slots, map,
active lock, session).

### Key features
| Feature | What it does | Where |
|---|---|---|
| **Barbershop profile** | Hero + 4 tabs: שירותים (menu), תורים פנויים (live slots), תיק עבודות (portfolio), חוות דעת (Google + in-app reviews). Graceful-degrades on null price/duration/barber. | `renderBarberView`, `js/shopData.js` |
| **Location / onboarding** | Non-hanging geolocation (`locateSafely` races a hard timeout → Jerusalem fallback, never freezes). Dynamic city search with geocode fallback. | `js/geo.js`, `renderVerifyView` |
| **Map** | Google Maps dark style; gold pins; **viewport-driven fetch** — pan/zoom → "חפש באזור זה" reloads shops for the visible bounds (center+radius via the radius API). Pin → preview → profile. | `js/map.js`, `fetchShopsForView` |
| **Home** | Capped-to-5 carousels (תורים זמינים בקרבתך / מבצעי דקה תשעים / מדורגים בקרבתך) each with a "ראה הכל" full-list page (`#/list/<kind>`); 5-shop rail + `#/shops`. | `renderNearbySlots`/`renderDeals`/`renderTopRated`/`renderListView` |
| **Filters** | Service / budget / date / rating / distance / open-now; Apply cascades to **map pins + list + carousels** from one `visibleShops()`/`visibleSlots()` pipeline. | `openFilterSheet`, `visibleShops` |
| **Login / registration** | **Phone SMS-OTP** via the RTL modal (`js/auth.js` → `/auth/send-otp` → `/auth/verify-otp`), storing a GoTrue session. A registration step captures Name + optional **profile photo → Supabase Storage** (public `avatars` bucket, keyed by `device_id`; base64 fallback). | `js/auth.js`, `renderRegisterView`, `js/storage.js` |
| **Booking flow** | Tap slot → pessimistic **lock** (300s countdown) → confirm sheet **pre-filled** with registered name/phone → `POST /bookings/confirm` → slot booked in DB → success. History via `/bookings`. | `bookSlot`/`booking.js`/`openConfirmSheet` |
| **Favorites** | Heart on the profile toggles a `localStorage` favorites set; "המועדפים שלי" (`#/favorites`) lists saved shops. | `toggleFavorite`, `renderFavoritesView` |
| **Payments** | Add-card form (number/expiry/CVV, live formatting + validation) with a mock "מאמת…" verification step; saves a masked card. | `openAddCardSheet` |

### Mock data (`scripts/` at repo root)
Node scripts (`@supabase/supabase-js`, service role from root `.env`) that seed realistic data for
testing — kept idempotent and tagged `google_place_id = 'seed:%'` for easy cleanup:
- `seed_barbershops.js` — 57 shops across 13 cities (Kiryat Shmona → Eilat) with PostGIS locations.
- `seed_relations.js` — per shop: 2–4 staff, a service menu, and future free slots for every barber.

### Run the consumer app
```bash
# from repo root — backend (data) + static frontend
cd backend && ../venv/bin/uvicorn app.main:app --port 8000 &
cd frontend/consumer && python3 -m http.server 3001    # open http://localhost:3001
```
First load runs onboarding (splash → role → verify → register). To replay: `localStorage.clear()`
in the console, then reload.

---

## Barber Dashboard (Phase 6)

A **separate** buildless app in `frontend/dashboard/` — **React via CDN + htm** (no build step),
Tailwind CDN with the Stitch barber design tokens, RTL. Unlike the anonymous consumer, barbers have
**real accounts via Supabase Auth**; the dashboard reads/writes **directly through `supabase-js`
under the owner RLS** (no backend data API). Live updates via Supabase Realtime on `bookings` +
`available_slots`.

- **Auth:** email + password (`js/auth.js`, `js/supabaseClient.js` with `persistSession`). Self-serve
  signup creates a **pre-confirmed** account through a dev-only backend endpoint
  (`POST /admin/barber-signup`, service-role) so onboarding works without an email inbox; global
  email confirmation stays on. On login the app finds the shop where `owner_id = auth.uid()` →
  dashboard, or runs onboarding (which inserts the shop with that owner).
- **Onboarding** (`js/onboarding.js`): business details + working hours → services → staff →
  bank/payment → calendar-sync, from the Stitch mockups (`_50/_1/_7/_2/_33`).
- **Dashboard** (`js/dashboard.js`): five tabs —
  - **Calendar** — day picker + active-staff filter, summary tiles, appointment timeline (client
    name/phone/service/time joined from `bookings`+`available_slots`) and free-slot management.
  - **Statistics** — per-employee selector + period filter (month/3m/6m/year/all); revenue / visits /
    average + dynamic SVG charts.
  - **Employees / Services** — full CRUD with **active/inactive toggles**.
  - **Settings** — business info, **change password (re-authentication required)**, sign out.
- **Data layer** (`js/data.js`): owner reads/writes via `unwrap()` (logs + rethrows errors, so
  failures surface instead of hanging). Shared `ConfirmModal` guards all destructive actions.

### Run the dashboard
Served by the same unified server (see Quick start): **http://localhost:4000/dashboard/index.html**,
or via the landing at `http://localhost:4000/`. Log in with `barber@torli.dev` / `torli1234`.
Re-seed the demo barber + ownership with `node scripts/seed_barber.js`.

---

## Authentication

Both audiences are unified on **Supabase Auth (GoTrue)**. *(Branch `feature/auth-layer` — pending
live verification; not yet merged.)*

**Barbers — email / password.** Unchanged: the dashboard logs in client-side with
`supabase.auth.signInWithPassword` (`frontend/dashboard/js/auth.js`); the dev-only
`POST /admin/barber-signup` (service-role) pre-creates confirmed accounts for onboarding. Owner RLS
keys on `auth.uid()` → `barbershops.owner_id`. There is intentionally **no backend `/auth/login`** —
it would duplicate what the dashboard already does directly.

**Clients — phone SMS-OTP.** Two thin wrappers over GoTrue (`backend/app/routers/auth.py`):

| Endpoint | Calls | Returns |
|---|---|---|
| `POST /auth/send-otp` | `auth.sign_in_with_otp({phone})` | `{success}` — GoTrue sends the SMS via the Twilio provider |
| `POST /auth/verify-otp` | `auth.verify_otp({phone, token, type:"sms"})` | `SessionResponse` — `access_token` + `refresh_token` + `user_id` |

Phone numbers are normalised to E.164 (Israeli `05x…` → `+972…`) in the Pydantic model. GoTrue owns
code generation, hashing, expiry, attempt-lockout, and rate-limiting — **we never store OTP codes**.

**Sessions & request auth.** Clients and barbers both hold GoTrue JWTs (short-lived access token +
rotating refresh token). The consumer stores the session in `localStorage` (`torli_session`) and
sends `Authorization: Bearer …` on booking/review calls. The backend validates it in
`backend/app/dependencies.py`:
- `get_current_user` — strips the bearer, calls `auth.get_user(token)`, returns the caller (401 on
  missing/invalid/expired).
- `get_authed_supabase` — returns a per-request Supabase client with the JWT applied
  (`client.postgrest.auth(token)`) so **`auth.uid()` resolves inside the RPCs**.

**Schema.** `public.users` (role `client|barber|owner`, PK → `auth.users.id`) is the profile table;
new auth users get a `role='client'` row automatically via the `handle_new_user` trigger. The
consumer migration drops the old `p_user` argument from `lock_slot` / `release_slot` /
`confirm_booking` / `cancel_booking` / `bookings_for_user` / `submit_review` — they now read
`auth.uid()` — and **revokes `anon` execute, granting `authenticated`**. Migrations:
`20260629140000_auth_profile_trigger.sql`, `20260629140100_bookings_use_auth_uid.sql`.

> ⚠️ **Release ordering (breaking change).** The `auth.uid()` migration revokes `anon` from the
> booking RPCs. The two migrations **and** the JWT-sending frontend must ship together, and Twilio
> must be configured in **Supabase Dashboard → Auth → Phone** (credentials live there, never in our
> `.env`). Deploying code without the migrations applied — or vice-versa — breaks booking.

**Twilio credentials** are configured in the Supabase Auth dashboard, **not** in this repo. The
`TWILIO_*` vars in `config.py` are for the separate, parked SMS-confirmation feature and are *not*
read by OTP login.

---

## Testing & QA

**Backend unit tests:** **229 passing** (+1 integration auto-skipped when no live backend), ~93%
branch coverage, mypy `--strict` + ruff + black clean. All external services — Supabase, GoTrue,
OpenAI, Google, Playwright — mocked (no network). `cd backend && ../venv/bin/python -m pytest tests/ -q`.
Auth coverage lives in `tests/test_auth.py` (OTP send/verify + the JWT dependencies).

**End-to-end QA pass:** a 20-scenario manual/automated suite ([`docs/qa_test_plan.md`](docs/qa_test_plan.md))
was executed against the live stack — **all passing**:

| Group | Scenarios verified |
|---|---|
| **Happy path (consumer)** | Unified landing routing; onboarding + registration (name/phone/avatar→Storage); geolocation fallback (no freeze) + viewport map; full booking (lock→confirm→DB); **live realtime reflection in the dashboard** (toast + bell badge). |
| **Resilience & security** | No double-booking (2nd lock → 409, one booking only); guest cannot read `bookings` (RLS "permission denied"); cross-shop owner isolation (owner sees only their shop); network-failure mid-booking shows an error toast (no silent fail / no hang); dashboard never hangs on load failure (error + retry). |
| **Dashboard stress** | Service/staff active↔inactive toggles with immediate global consumer + operational filtering; confirmation modals on all destructive actions (cancel = no-op); re-authentication gate blocks a password change with a wrong current password; notifications bell dropdown of unseen appointments. |
| **Data integrity** | Statistics recompute per-staff and per-period; loyalty aggregates by phone (visits / spend / last visit); **availability overrides** hide blocked slots from consumers (`free_slots`) and `lock_slot` rejects a blocked slot ("time blocked by the shop"). |

### Production-readiness
The consumer + barber dashboard MVP is **feature-complete and verified**. Security rests on
Postgres RLS (owner-scoped policies + `SECURITY DEFINER` booking RPCs); the service-role key is
never exposed to the browser. Intentional, documented constraints before a real launch:

- **Consumer accounts** are phone SMS-OTP (Supabase Auth) on branch `feature/auth-layer` — booking
  requires a verified session. *(On `main` today the consumer is still the anonymous `torli_user_token`
  model; the auth layer lands once live-verified.)* See [Authentication](#authentication).
- **Payments are mock** (card form + simulated verification) — no real charge/PSP integration.
- **Booking submission** to external sites is gated by `BOOKING_LIVE` (default `false` = dry run);
  in-DB partner shops book directly. Set `BOOKING_LIVE=true` only after validating real sites.
- The dev-only `POST /admin/barber-signup` (pre-confirmed accounts) and the admin ops router are
  mounted **only when `ENVIRONMENT != production`**.

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
│   └── migrations/     # SQL schema + SECURITY DEFINER RPCs + avatars Storage bucket
├── frontend/
│   ├── consumer/       # buildless SPA (js/app.js orchestrator, api/geo/map/state/storage/shopData)
│   ├── dashboard/      # barber dashboard (React-via-CDN; next phase)
│   └── stitch/         # design-reference mockups the UI targets
├── scripts/            # Node seed scripts (mock barbershops + relations)
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
- `auth.py` — client phone-OTP login (`/auth/send-otp`, `/auth/verify-otp`); see [Authentication](#authentication).
- `barbershops.py` — shop search + PostGIS radius. `slots.py` — slot lists / nearby.
- `bookings.py` — lock → confirm → cancel flow (JWT-scoped). `reviews.py` — in-app reviews (JWT-scoped).
- `admin.py` — dev-only ops triggers (mounted when `ENVIRONMENT != production`):
  `/admin/discovery/run`, `/admin/scraping/run`, **`/admin/enrichment/run`**, `/admin/barber-signup`.
- `dependencies.py` — shared `get_current_user` / `get_authed_supabase` JWT auth dependencies.

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
tables; owner-scoped writes; service-role for agents. The auth-layer migrations
(`*_auth_profile_trigger.sql`, `*_bookings_use_auth_uid.sql`) add the `handle_new_user` profile
trigger and move the booking/review RPCs onto `auth.uid()` (see [Authentication](#authentication)).

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

> **Auth note:** client phone-OTP uses Twilio, but those credentials live in **Supabase Dashboard →
> Auth → Phone**, *not* in `.env`. The `TWILIO_*` vars above are only for the parked SMS-confirmation
> feature. JWTs are validated against GoTrue (no signing secret needed); set the optional
> `SUPABASE_JWT_SECRET` only if switching to local HS256 verification later.

## Known limitations (best-effort by design)
- Google Places exposes no staff / per-barber menus / durations; those come only from booking
  pages, many of which are app-walled or absent — coverage is partial, absent fields stay `null`.
- `upsert_service` is `ON CONFLICT DO NOTHING` (first-write-wins) — re-enrichment doesn't backfill
  existing rows yet.
- Real per-barber prices require logged-in booking-widget integration (future).
