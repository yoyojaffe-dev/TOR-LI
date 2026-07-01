<div dir="rtl">

# תּוֹר-לי (Tor-Li) — הזמנת תספורות של הרגע האחרון

</div>

**Tor-Li** — a real-time, location-based web app for booking **last-minute haircuts** at Israeli men's barbershops. A user opens the app, shares their location, and immediately sees free slots at nearby barbershops — then books in a few taps. Behind the scenes, autonomous background agents continuously discover barbershops from Google Maps, enrich their profiles, and scrape their booking pages for open slots.

<div dir="rtl">

## סקירה כללית (Project Overview)

**מה זה תּוֹר-לי?** אפליקציית ווב מבוססת-מיקום בזמן אמת להזמנת תספורות של הרגע האחרון.
הבעיה: לספָּרים יש חלונות פנויים שנוצרים בביטולי-רגע וב"חורים" ביומן, וללקוחות אין דרך
נוחה למצוא תור פנוי *עכשיו* בקרבת מקום. תּוֹר-לי פותר את זה: המשתמש רואה על מפה את המספרות
הקרובות אליו עם החלונות הפנויים הקרובים בזמן, ומזמין בכמה הקשות — כולל נעילת התור למשך
5 דקות כדי להשלים את ההזמנה ללא חשש שמישהו אחר יתפוס אותו.

**קהל היעד:** מספרות גברים בישראל (ולקוחותיהן). הממשק כולו בעברית / RTL.

**הצעת הערך המרכזית:** גילוי חלונות פנויים בזמן אמת + הזמנה בהקשה אחת.

</div>

**Core value proposition (EN):** real-time free-slot discovery near the user + one-tap booking, with a pessimistic 5-minute lock so a slot can't be double-booked while a customer checks out.

> Live Supabase project: `ekugfzrmitvoiamevtfa`. Hebrew / RTL frontend. Buildless vanilla-JS consumer app.

---

## 2. Live Demo / דמו חי

| Surface | URL |
|---|---|
| **Backend API** | https://tor-li-production.up.railway.app |
| **Frontend (consumer)** | https://frontend-production-2c43.up.railway.app |
| **Health probe** | https://tor-li-production.up.railway.app/health |

**Demo barber (dashboard) login:** `barber@torli.dev`
Password: _provided separately in the presentation notes — deliberately **not** committed to this public repository (a plaintext credential in git history would be permanently exposed and search-indexed)._

> ⚠️ **Auth status:** barber/consumer authentication (Supabase Auth OTP) currently lives on the `feature/auth-layer` branch and is **not yet merged to `main`**. On `main`, the barber dashboard authenticates against Supabase Auth for owner-scoped data, while the consumer app is anonymous (per-browser `user_token`). See §8 and §17.

---

## 3. Tech Stack / מחסנית טכנולוגית

| Layer | Technology | Notes |
|---|---|---|
| **Backend** | Python 3.11 · FastAPI | Sync route handlers run in FastAPI's threadpool; one `async` admin endpoint |
| **Database** | Supabase — PostgreSQL + **PostGIS** | `geography(Point,4326)` for radial search; RLS-enforced |
| **DB access** | `supabase-py` (sync SDK) | Two roles: anon (RLS) vs service-role (agents, bypasses RLS) |
| **Booking safety** | Atomic SQL RPCs (`SECURITY DEFINER`) | Pessimistic locking lives in the DB, not the app |
| **Scraping / booking** | **Playwright** (headless Chromium) | Mobile iPhone UA, `he-IL` locale |
| **AI extraction** | **OpenAI `gpt-4o-mini`** | Tool/function-calling for classify / extract-slots / profile / form-fill |
| **Discovery data** | **Google Maps / Places API** | `places_nearby` + Place Details |
| **Frontend (consumer)** | Vanilla JS ES Modules · **Tailwind (CDN)** | Buildless — no bundler, no `package.json` |
| **Frontend (dashboard)** | React-via-CDN + `htm` · Tailwind (CDN) | Buildless barber dashboard |
| **Deployment** | **Railway** (Nixpacks) | Backend = uvicorn; frontend = `python -m http.server` |
| **SMS OTP** | Twilio | **Planned** — config keys exist in `config.py`; work parked on `sms-confirmation` branch |

---

## 4. System Architecture / ארכיטקטורת מערכת

The three surfaces share **no in-process coupling** — they communicate only through Postgres (a "message board"). The API serves the same tables the agents write.

```
                        ┌────────────────────────────────────────────────┐
                        │                   USERS                         │
                        │   Consumer (GPS) ·····  Barber (dashboard)       │
                        └───────┬───────────────────────────┬─────────────┘
                                │ HTTPS / hash-router SPA    │ React-via-CDN
                                ▼                            ▼
             ┌──────────────────────────────┐   ┌───────────────────────────┐
             │  Consumer frontend           │   │  Dashboard frontend       │
             │  (vanilla JS ES modules)     │   │  (React-CDN + htm)        │
             └───────┬───────────────┬──────┘   └──────┬────────────┬───────┘
                     │ REST          │ Realtime WS      │ REST       │ Realtime WS
                     ▼               │                  ▼            │
        ┌────────────────────────┐   │      ┌────────────────────────┐
        │  FastAPI backend       │   │      │  dashboard reads/writes │
        │  /barbershops /slots   │   │      │  go direct to Supabase  │
        │  /bookings /reviews    │   │      │  under owner RLS via    │
        │  /geocode  /admin(dev) │   │      │  data.js                │
        └───────────┬────────────┘   │      └────────────────────────┘
                    │ anon key (RLS) + SECURITY DEFINER RPCs
                    ▼               │
        ╔═══════════════════════════▼══════════════════════════════════════╗
        ║           SUPABASE  ·  PostgreSQL + PostGIS                       ║
        ║                                                                   ║
        ║  barbershops · available_slots · bookings · reviews ·             ║
        ║  external_reviews · staff · services · users · appointments ·     ║
        ║  availability_overrides                                           ║
        ║                                                                   ║
        ║  ▲ Realtime publication: available_slots, bookings  ─────────────╫──▶ WS
        ╚═══▲═══════════▲═══════════════▲═══════════════▲═══════════════════╝
            │ service-role key (bypasses RLS) — AGENTS ONLY
            │           │               │               │
    ┌───────┴──┐  ┌─────┴──────┐  ┌─────┴───────┐  ┌────┴──────────┐
    │DISCOVERY │  │ ENRICHMENT │  │  SCRAPING   │  │   BOOKING     │
    │ Google   │  │ Playwright │  │  Playwright │  │  Playwright   │
    │ +OpenAI  │  │  +OpenAI   │  │   +OpenAI   │  │  +OpenAI(gen) │
    ├──────────┤  ├────────────┤  ├─────────────┤  ├───────────────┤
    │writes:   │  │writes:     │  │writes:      │  │writes: (none) │
    │barbershops│ │staff       │  │available_   │  │returns success│
    │external_ │  │services    │  │  slots      │  │→ router calls │
    │reviews   │  │enriched_at │  │             │  │  confirm RPC  │
    └──────────┘  └────────────┘  └─────────────┘  └───────────────┘
```

**Data flow summary:** Discovery seeds `barbershops` (+ `external_reviews`) from Google → Enrichment fills `staff`/`services` from each booking page → Scraping keeps `available_slots` fresh in a loop → the consumer reads slots (live via Realtime) and books → the Booking Agent drives the barber's real booking site → `confirm_booking` RPC flips the slot to `booked` → Realtime pushes the new booking to the dashboard.

---

## 5. Data Model / מודל נתונים

All tables live in the `public` schema. Mutations to discovery tables route through **`SECURITY DEFINER` RPCs**; both frontend and backend use the anon key. `service_role` (agents) bypasses RLS.

### `barbershops`
Discovered shops. **Written by:** Discovery Agent (`upsert_barbershop` RPC) + owner edits (dashboard).
Key columns: `id uuid PK`, `name`, `address`, `phone`, `booking_url`, `google_place_id UNIQUE` (upsert conflict key), `location geography(Point,4326)` (GiST-indexed), `opening_hours jsonb`, `owner_id → users(id)`, `photo_url`, `photo_urls jsonb`, `place_type`, `rating`, `rating_count`, `booking_platform`, `enriched_at`, `google_types jsonb`, `is_active_partner`.
**RLS:** public SELECT (anon+auth); INSERT/UPDATE only by owner (`owner_id = auth.uid()`); service_role has insert/update. No DELETE.

### `available_slots`
Bookable time slots. **Written by:** Scraping Agent (`upsert_free_slot`), locking RPCs, owner edits.
Key columns: `id uuid PK`, `barbershop_id → barbershops (cascade)`, `service_name`, `price numeric(10,2)`, `slot_time timestamptz`, `status ∈ {free,locked,booked}` (enum), `locked_until`, `locked_by`, `staff_id → staff`. UNIQUE `(barbershop_id, slot_time, service_name)`.
**RLS:** public SELECT; INSERT/UPDATE/DELETE by shop owner (`is_shop_owner`). **In the Realtime publication.**
> ⚠️ **Drift:** `is_deal` / `deal_price` are read by the `bookings_for_user` RPC but exist only in the **live DB** — no migration file creates them. Documented here as a known repo/DB drift to reconcile.

### `bookings`
Confirmed customer bookings (private). **Written by:** `confirm_booking` / `cancel_booking` RPCs only.
Key columns: `id uuid PK`, `slot_id → available_slots (cascade)`, `customer_name`, `customer_phone`, `status` (default `confirmed`), `user_token` (opaque per-browser token — **not** `auth.uid()`).
**RLS:** no anon SELECT (intentionally private); shop owner may SELECT their shop's bookings. **In the Realtime publication** (drives dashboard notifications).

### `reviews`
In-app reviews, one per booking. **Written by:** `submit_review` RPC.
Key columns: `id uuid PK`, `booking_id → bookings UNIQUE`, `barbershop_id → barbershops`, `user_token`, `rating int (1–5)`, `comment`.
**RLS:** no direct table policies — **access is RPC-only** (`submit_review`, `reviews_for_barbershop`, both `SECURITY DEFINER`).

### `external_reviews`
Scraped Google reviews (kept separate from in-app `reviews`). **Written by:** Discovery Agent (`upsert_external_review`).
Key columns: `id uuid PK`, `barbershop_id → barbershops`, `author`, `rating numeric`, `text`, `source` (default `google`), `reviewed_at`. Dedup unique index on `(barbershop_id, source, md5(author|text))`.
**RLS:** public SELECT; writes = service_role only.

### `staff`
Employees per shop. **Written by:** Enrichment Agent (`upsert_staff`) + owner edits.
Key columns: `id uuid PK`, `shop_id → barbershops (cascade)`, `name`, `is_active`. Unique `(shop_id, lower(name))`.
**RLS:** public SELECT; INSERT/UPDATE/DELETE by owner; full DML to service_role.

### `services`
Service menu per shop. **Written by:** Enrichment Agent (`upsert_service`, gap-fill) + owner edits.
Key columns: `id uuid PK`, `shop_id → barbershops (cascade)`, `name`, `duration_mins` (nullable), `price` (nullable), `staff_id → staff`, `category`, `is_active`. Unique `(shop_id, lower(name), staff_id)`.
**RLS:** public SELECT; INSERT/UPDATE/DELETE by owner; full DML to service_role.

### `users`
Profiles coupled 1:1 to `auth.users`. **Written by:** dashboard signup / admin `barber-signup`.
Key columns: `id uuid PK → auth.users(id)`, `role ∈ {client,barber,owner}`, `full_name`, `phone`.
**RLS:** each row readable/writable only by its own `auth.uid()`; service_role full DML; anon = nothing.

### `appointments` (spec-parallel, currently unused)
Owner-scoped appointment table parallel to `bookings`. `client_id → users`, `slot_id → available_slots UNIQUE`, `status ∈ {pending,confirmed,completed,cancelled}`. Client-owned + shop-owner-readable RLS. Present in migrations; empty in practice (the live flow uses `bookings`).

### `availability_overrides`
Owner blockers (whole-shop or per-staff), local Asia/Jerusalem time. `barbershop_id`, `staff_id?`, `date`, `all_day`, `start_time`, `end_time`, `note`. Public SELECT; owner-only writes. Consumed by the `is_slot_blocked` / `free_slots` RPCs so blocked slots never surface as free.

### Key RPCs (all `SECURITY DEFINER` unless noted)
`lock_slot` · `release_slot` · `confirm_booking` (5-arg: flips slot→booked **and** inserts the booking atomically) · `cancel_booking` · `upsert_free_slot` (never resets a locked/booked slot) · `upsert_barbershop` · `barbershops_within_radius` (`stable`) · `available_slots_nearby` (`stable`) · `bookings_for_user` (deal-aware) · `submit_review` · `reviews_for_barbershop` · `upsert_staff` · `upsert_service` (gap-fill) · `upsert_external_review` · `is_slot_blocked` · `free_slots`.
`is_shop_owner(uuid)` is the ownership predicate for RLS — hardened to **`SECURITY INVOKER`** with restricted EXECUTE.

---

## 6. The Agents / הסוכנים

Four production agents (+ a one-off `reclassify` remediation agent). All use the **service-role** client (bypasses RLS) and the OpenAI **`gpt-4o-mini`** model via tool-calling. Source: `backend/app/agents/`.

### 🔍 Discovery Agent — `discovery_agent.py`
- **Role:** find men's barbershops near a coordinate; populate `barbershops`.
- **Flow:** `discover(lat, lng, radius_m=5000)` → Google `places_nearby` over `["barber_shop","hair_care"]` → Place Details → **AI classify** (`classify_barbershop` tool, strict boolean `is_mens_barbershop`) → `upsert_barbershop` RPC → follow-up UPDATE for `opening_hours` → `upsert_external_review` for filtered Google reviews.
- **APIs:** Google Maps Places (sync SDK, off-loaded via `asyncio.to_thread`) + OpenAI.
- **Concurrency:** `asyncio.Semaphore(5)` (`_MAX_CONCURRENT_FILTER = 5`).
- **Failure model:** **fails closed** — any classifier exception → `False` → shop skipped, never written. Per-candidate errors logged & skipped (`gather(return_exceptions=True)`).
- **CLI:** `python -m scripts.run_discovery --lat 32.0853 --lng 34.7818 --radius 5000`

### 🧩 Enrichment Agent — `enrichment_agent.py`
- **Role:** fill barber profiles — `staff` (team) + `services` (menu) — from each booking page. Decoupled from scraping.
- **Flow:** select shops (`booking_url` set, `place_type ∈ {barber_shop,hair_care}`, stalest `enriched_at` first, limit) → Playwright load page → **profile extractor** (`gpt-4o-mini`) → `upsert_staff` / `upsert_service` → stamp `enriched_at`.
- **Guards:** skip pages < 200 chars (still stamp `enriched_at`); keep price/duration only from **trusted platforms** (`tor4you, glamera, calmark, eztor, cutshave`); hard-negative prompt against fabricating staff/services.
- **Concurrency:** `asyncio.Semaphore(5)`; default 50 shops/pass.
- **Failure model:** per-shop try/except → zero counters, logged; not fails-closed.
- **CLI:** `python -m scripts.run_enrichment --limit 50`

### 🕷️ Scraping Agent — `scraping_agent.py`
- **Role:** continuous loop scraping each shop's booking page → sync open slots to `available_slots`.
- **Flow:** select shops with `booking_url` (skips facebook/instagram/twitter/t.me) → Playwright (timeout 20s, render wait 2.5s, `body` text capped 15k chars) → **`extract_slots`** tool (`gpt-4o-mini`) → `upsert_free_slot` RPC (never resets locked/booked slots).
- **Concurrency:** `asyncio.Semaphore(5)` (`_MAX_CONCURRENT_SHOPS = 5`); one shared browser, per-shop contexts.
- **Failure model:** per-shop try/except → 0 slots, logged; loop catches per-pass errors and continues; re-raises `CancelledError`.
- **CLI:** `python -m scripts.run_scraping --loop --interval 300` (or one-shot without `--loop`).

### 📅 Booking Agent — `booking_agent.py`
- **Role:** on-demand worker triggered by `POST /bookings/confirm`; drives the barber's real booking site via Playwright.
- **Flow:** `submit(slot_id, name, phone)` → read slot+shop → `detect_platform(url)` → static adapter (**Tor4You** / **Glamera**, selectors still placeholder) or **`GenericAIAdapter`** (`fill_booking_form` tool) → fill form.
- **Live vs dry-run:** gated by `BOOKING_LIVE` (**default `false` = dry run**: fills, skips the submit click — no real appointment). Live submit is irreversible.
- **Concurrency:** **none** — single on-demand invocation, one browser per `submit`. (No semaphore, no `run_booking.py` CLI — API-triggered only.)
- **Writes:** none directly; returns `{success, ...}` and the router releases the lock / returns 502 on failure.

### ♻️ Reclassify Agent — `reclassify_agent.py`
One-off backfill: subclasses Discovery to reuse its classifier; re-fetches only Google `types` for legacy rows, re-classifies, and demotes non-barbershops (`place_type='non_barber'`). CLI: `python -m scripts.run_reclassify --limit N`.

**Orchestrator:** `scripts/run_agents.py` runs one Discovery pass (point or `--national` grid) then the Scraping loop (Booking excluded). `main.py` starts the Scraping loop on boot **only when `AGENTS_AUTOSTART=true`**.

> 💸 **Cost warning:** every agent runner hits **live** Google / OpenAI / Supabase and bills real money. They are excluded from CI (tests mock all of it).

---

## 7. API Reference / ממשק API

Base URL: `https://tor-li-production.up.railway.app`. "Auth" below = the app-level `user_token` (an anonymous per-browser token), **except** `/geocode`, which requires a real Supabase Auth session. All response filtering (e.g. hiding `user_token`) is enforced by `response_model`.

| Method | Path | Auth | Body | Response | Description |
|---|---|---|---|---|---|
| GET | `/health` | — | — | `{status,service,environment}` | Liveness probe |
| GET | `/barbershops?lat&lng&radius=2000` | — | — | `list[Barbershop]` | Shops within radius (m), nearest first (PostGIS) |
| GET | `/barbershops/{id}` | — | — | `Barbershop` | One shop; 404 if missing |
| GET | `/slots?barbershop_id&only_free=true` | — | — | `list[Slot]` | Upcoming slots for a shop (not time-filtered when raw) |
| GET | `/slots/nearby?lat&lng&radius=5000&limit=20` | — | — | `list[NearbySlot]` | Free **future** slots near a point + shop info |
| GET | `/slots/realtime-info` | — | — | `object` | Realtime channel/table info for the frontend |
| GET | `/bookings?user_token=…` | `user_token` (query) | — | `list[BookingHistoryItem]` | Caller's bookings, newest first |
| POST | `/bookings/lock` | `user_token` (body) | `LockRequest` | `LockResponse` | Acquire pessimistic slot lock (409 if unavailable) |
| POST | `/bookings/release` | `user_token` (body) | `LockRequest` | `LockResponse` | Release a held lock |
| POST | `/bookings/confirm` | `user_token` (body) | `BookingRequest` | `BookingResponse` (201) | Run Booking Agent, then flip slot → booked (502 on live submit failure) |
| POST | `/bookings/cancel` | `user_token` (body) | `CancelRequest` | `ActionResult` | Cancel a booking + free the slot (409 on failure) |
| POST | `/reviews` | `user_token` (body) | `ReviewRequest` | `ActionResult` | Submit/update a review for a completed booking |
| GET | `/reviews?barbershop_id=…` | — | — | `list[Review]` | Recent reviews, masked names |
| GET | `/geocode?address=…` | **Supabase Auth** | — | `GeocodeResult` | Address → `{lat,lng}` (Google); 503/502/404 on error |

**Admin router — mounted only when `ENVIRONMENT != production`** (triggers billed work):

| Method | Path | Body | Description |
|---|---|---|---|
| POST | `/admin/barber-signup` | `BarberSignupRequest` | Dev: create pre-confirmed barber + owner `users` row |
| POST | `/admin/discovery/run?lat&lng&radius_m` | — | One Discovery pass |
| POST | `/admin/scraping/run` | — | One Scraping pass (async) |
| POST | `/admin/enrichment/run?limit=50` | — | One Enrichment pass |

> There is **no `/auth/*` router on `main`.** Full consumer/barber OTP auth is on `feature/auth-layer` (§17).

---

## 8. Security Model / מודל אבטחה

1. **Row-Level Security (RLS).** Both frontend and backend use the **anon key**; every table has explicit policies. Owner-scoped tables (`barbershops`, `services`, `staff`, `available_slots`, `availability_overrides`, `appointments`, `users`) restrict writes to the row owner via `auth.uid()` / `is_shop_owner(shop_id)`.
2. **`SECURITY DEFINER` RPCs.** Discovery/booking mutations run through definer-rights functions with a pinned `search_path=public`, so anon callers can perform *exactly* the audited operation (lock, confirm, upsert) and nothing else — the app never holds broad table-write grants.
3. **Ownership predicate hardened.** `is_shop_owner` was moved to **`SECURITY INVOKER`** with EXECUTE revoked from anon/public — it can't be abused to probe ownership.
4. **Pessimistic slot locking is in the database.** `lock_slot` atomically sets `status='locked'`, `locked_by`, `locked_until = now()+TTL` and rejects blocked slots; `confirm_booking` flips → `booked` and inserts the booking in one atomic statement. **Double-booking is impossible at the SQL level** — never reimplemented in Python.
5. **Admin router env-gated.** Mounted only when `ENVIRONMENT != production`, because it triggers billed agent work.
6. **Service-role key never reaches the browser.** It's used exclusively by background agents (`get_supabase_admin`); the frontend only ever sees the anon key.
7. **JWT / Supabase Auth (dashboard).** The barber dashboard uses Supabase Auth (GoTrue) with `persistSession` + `autoRefreshToken`; `/geocode` is the one backend endpoint gated on a valid session. Consumer-side OTP auth is on `feature/auth-layer`.

---

## 9. Real-Time Sync / סנכרון בזמן אמת

Supabase Realtime (`postgres_changes`) is enabled on `available_slots` and `bookings`.

- **Consumer — `subscribeToSlots({barbershopId, onChange})`** (`consumer/js/realtime.js`): opens channel `slots:<id>` (or `slots:all`) listening to `available_slots` changes, filtered `barbershop_id=eq.<id>` when scoped. When a slot is locked/booked elsewhere it **disappears from the map/list live**, with no refresh.
- **Dashboard — `subscribeShop(shopId, cb)`** (`dashboard/js/data.js`): channel `owner:<shopId>` with two listeners — `available_slots` (filtered to the shop) and `bookings` (unfiltered) — so a **new booking appears on the calendar instantly** and rings the notifications bell.
- **Dashboard — `onAuthChange`** (`dashboard/js/auth.js`): wraps `supabase.auth.onAuthStateChange`, surfacing `SIGNED_IN` / `SIGNED_OUT` / `TOKEN_REFRESHED`. `app.js` uses it as the identity gate that drives auth-screen → onboarding → dashboard transitions.
- **15s polling (services menu only).** On the barbershop-profile view the consumer polls `loadServiceMenu()` every 15 000 ms to refresh the price list (`available_slots` on that view stay live via Realtime, not the poll). A separate 1 000 ms interval drives the lock countdown in `booking.js`.

---

## 10. Booking Flow / זרימת הזמנה

```
User taps a free slot
      │
      ▼
POST /bookings/lock ──▶ lock_slot RPC (atomic): status='free'→'locked',
      │                 locked_by=user_token, locked_until=now()+300s
      ▼
Client 5-minute countdown  (booking.js, 1s interval)
      │   ├─ expires → POST /bookings/release → release_slot → status='free'
      │   └─ user confirms ▼
POST /bookings/confirm
      │
      ▼
BookingAgent.submit(slot, name, phone)   (Playwright + adapter/AI)
      │   ├─ BOOKING_LIVE=false → dry run (fills, no submit click)
      │   └─ success ▼
confirm_booking RPC (atomic): slot status='booked' + INSERT bookings row
      │
      ▼
Realtime push:  available_slots change → consumer removes slot;
                bookings insert → dashboard calendar + notification toast
```

Slot lock TTL = **300 s** (`slot_lock_ttl_seconds`), matching the Stitch checkout UX.

---

## 11. Frontend Architecture / ארכיטקטורת פרונטאנד

**Consumer app** — `frontend/consumer/js/` — buildless hash-router SPA:

| File | Responsibility |
|---|---|
| `app.js` | Orchestrator: geo → radius search → map → slots → booking; hash router |
| `booking.js` | Lock → countdown → confirm/auto-release flow |
| `api.js` | `fetch` wrappers around the FastAPI backend (`ApiError`) |
| `realtime.js` | `subscribeToSlots` — live `available_slots` updates |
| `map.js` | Google Maps: markers, radius circle, dark theme, ETAs |
| `geo.js` | GPS + manual address geocoding |
| `shopData.js` | Direct anon-read Supabase queries (services/staff/external reviews) |
| `state.js` | Observable store + per-browser `torli_user_token` |
| `storage.js` | Avatar upload to public `avatars` Storage bucket |
| `config.js` | Runtime config (env-gated backend URL, keys, `LOCK_TTL=300`, `RADIUS=2000`) |
| `supabaseClient.js` | CDN anon Supabase client (`eventsPerSecond: 10`) |

**Dashboard** — `frontend/dashboard/js/` — React-via-CDN + `htm`:

| File | Responsibility |
|---|---|
| `app.js` | Root: auth gate → onboarding (no shop) or `Dashboard`; wires `onAuthChange` |
| `dashboard.js` | Shell + **6-tab** bottom nav + notifications bell |
| `data.js` | Owner data layer (owner-RLS reads/writes) + `geocodeAddress` + `subscribeShop` |
| `auth.js` | Supabase Auth (sign in/out, session, reauth) + dev signup |
| `onboarding.js` | 5-step barber onboarding (business+hours → services → staff → payment → sync) |
| `ui.js` | Buildless React + `htm` binding + Stitch design-system widgets |
| `config.js` / `supabaseClient.js` | Runtime config / authenticated Supabase client |

**Dashboard tabs (6):** `לוח` (Calendar) · `לקוחות` (Loyalty/Customers) · `סטטיסטיקות` (Stats) · `עובדים` (Staff) · `שירותים` (Services) · `הגדרות` (Settings). Default tab: Calendar.

---

## 12. Deployment / פריסה

Deployed on **Railway** (Nixpacks), **auto-deploy from `main`**.

- **Backend service** — `backend/railway.json`: builder NIXPACKS, `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, healthcheck `/health`, restart ON_FAILURE (max 5). Root Directory = `backend/`. (`backend/Procfile` mirrors the start command.)
- **Frontend service** — `frontend/railway.json`: builder NIXPACKS, start `python3 -m http.server $PORT` (static), healthcheck `/`.

### Environment variables (`backend/app/config.py`, read from repo-root `.env`)

| Var | Default | Purpose |
|---|---|---|
| `SUPABASE_URL` | _(required)_ | Supabase project URL |
| `SUPABASE_KEY` | _(required)_ | Anon key (RLS-guarded paths) |
| `SUPABASE_SERVICE_ROLE_KEY` | `""` | Bypasses RLS — agents only |
| `GOOGLE_MAPS_API_KEY` | `""` | Discovery + geocoding |
| `OPENAI_API_KEY` | `""` | `gpt-4o-mini` extraction |
| `PAYMENT_API_KEY` | `mock_key_for_now` | Payment provider (mock) |
| `TWILIO_ACCOUNT_SID` / `_AUTH_TOKEN` / `_PHONE_NUMBER` | `""` | SMS OTP (planned) |
| `ENVIRONMENT` | `development` | Gates admin router (`!= production`) |
| `PORT` | `8000` | Server port |
| `SLOT_LOCK_TTL_SECONDS` | `300` | Pessimistic lock window |
| `BOOKING_LIVE` | `false` | Booking Agent submit kill-switch (dry run default) |
| `AGENTS_AUTOSTART` | `false` | Start Scraping loop on boot |

---

## 13. Git Workflow / זרימת עבודת Git

**Branch strategy:** `main` (production, auto-deploys) ← `develop` (integration) ← `feature/*` and `fix/*` (topic branches). Topic branches merge into `develop`; `develop` merges into `main` to release.

**Representative active branches:**
- `feature/auth-layer` — Supabase-native barber + client OTP auth (not yet on `main`).
- `feature/barber-dashboard-mvp`, `feature/booking-sheet`, `feature/unified-agents-cli`.
- `feat/consumer-live-services`, `feat/consumer-staff-display`, `feat/dashboard-deals-and-settings`, `feat/dashboard-price-cascade`, `feat/frontend-prod-config`.
- `fix/agents-place-type-filter`, `fix/widen-pricing-allowlist`, `fix/dashboard-realtime-and-cancel-notify`, `fix/deal-price-modal`, `fix/railway-deploy`.
- `sms-confirmation` — parked SMS reminder work.

**Recent production hotfixes (merged `develop` → `main`):** removed a dangling `useMyLocation` prop that crashed dashboard onboarding; excluded cancelled bookings from the profile total count.

---

## 14. Quick Start (local) / התחלה מהירה

```bash
# 1. Clone
git clone https://github.com/yoyojaffe-dev/TOR-LI.git && cd TOR-LI

# 2. Python venv at the repo root
python3.11 -m venv venv
venv/bin/pip install -r backend/requirements.txt
venv/bin/python -m playwright install chromium   # for scraping/booking agents

# 3. Secrets — .env at the REPO ROOT (shared by backend, Supabase CLI, frontend)
#    SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, GOOGLE_MAPS_API_KEY,
#    OPENAI_API_KEY, ENVIRONMENT=development ...

# 4. Run the API (from backend/)
cd backend
../venv/bin/uvicorn app.main:app --port 8000

# 5. Consumer frontend (from repo root, new shell)
cd frontend/consumer && python3 -m http.server 3001   # http://localhost:3001

# 6. Dashboard needs ?shop=<uuid>
cd frontend/dashboard && python3 -m http.server 3002   # open with ?shop=<uuid>
```

---

## 15. Running the Agents / הרצת הסוכנים

> 💸 These hit **live** Google / OpenAI / Supabase and **cost money**. Run deliberately.

```bash
# from backend/
../venv/bin/python -m scripts.run_discovery --lat 32.0853 --lng 34.7818 --radius 5000
../venv/bin/python -m scripts.run_national_discovery --cities haifa,eilat   # subset; omit for full sweep
../venv/bin/python -m scripts.run_enrichment --limit 50
../venv/bin/python -m scripts.run_scraping --loop --interval 120
../venv/bin/python -m scripts.run_reclassify --limit 200
../venv/bin/python -m scripts.run_agents            # Discovery once → Scraping loop
```

All runners share a CLI harness (`scripts/_cli.py`): `--version`, argparse validators, and clean Ctrl-C (exit 130). Log level via `LOG_LEVEL` (default INFO).

---

## 16. Testing / בדיקות

```bash
# from backend/
../venv/bin/python -m pytest tests/ -q                                  # unit (Supabase/agents mocked)
../venv/bin/python -m pytest tests/ -q --cov=app --cov-report=term-missing
../venv/bin/python -m mypy --strict          # scoped to app/
../venv/bin/ruff check app tests scripts
../venv/bin/black app tests scripts
```

**Current suite status on `main` (measured, `pytest --cov`):**

| Metric | Value |
|---|---|
| Passing | **204** |
| Failing | **1** — `test_national_discovery.py::test_grid_covers_ten_core_cities` |
| Skipped | 3 (integration tests; auto-skip when `localhost:8000` is down) |
| Branch coverage | **83.14%** (config gate: `fail_under = 90`) |

> ⚠️ **Honest status:** one test is currently **red** and coverage is **below the 90% gate**. The failing test is *stale, not a code bug* — the national-discovery grid was expanded to 25 cities, but the test still asserts an exact set of 10 "core" cities. It should be updated to assert the 10 core cities are a **subset** of the grid. Filed as a follow-up (see §17).

Tests are hermetic: unit tests mock Supabase (`MagicMock` / patched `get_supabase`) and never touch the network. `tests/test_*_integration.py` require a running backend and auto-skip otherwise. A Playwright E2E suite (`frontend/consumer/e2e/`) uses Page Objects + web-first waits and needs upcoming free slots in the DB to run fully.

---

## 17. Known Limitations & Roadmap / מגבלות וכיווני המשך

**Intentional gaps (by design — see `specs/torli_reverse_spec.md`):**
- Booking Agent defaults to **dry run** (`BOOKING_LIVE=false`) — no real appointment is created until validated against live sites.
- `GET /slots` is not time-filtered (returns past-dated free slots by design); `GET /slots/nearby` is the future-only path.
- Tor4You / Glamera booking adapters ship with **placeholder selectors** — not yet verified against real DOMs; unknown sites fall back to the AI form-mapper.

**Known issues to reconcile:**
- **DB/repo drift:** `available_slots.is_deal` / `deal_price` exist in the live DB but no migration creates them — add a migration to record them.
- **Failing/coverage gate:** fix the stale `test_grid_covers_ten_core_cities` assertion and restore ≥ 90% coverage.

**Roadmap:**
- **Auth layer** (`feature/auth-layer`): Supabase-native barber + client OTP; move the consumer off the anonymous `user_token`.
- **SMS confirmations/reminders** (`sms-confirmation`): wire the existing Twilio config into booking notifications.
- **Payments:** replace the mock `PAYMENT_API_KEY` with a real provider.
- **Migrate `bookings` → `appointments`** to converge on the spec-compliant, client-scoped table.

---

<div dir="rtl">

*תּוֹר-לי — נבנה עם FastAPI · Supabase/PostGIS · Playwright · OpenAI · Railway.*

</div>
