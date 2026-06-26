# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Tor-li — real-time, location-based web app for booking **last-minute haircuts**. A user
sees free slots near their GPS/searched location and books in a few taps. Background
agents discover barbershops from Google Maps and scrape their booking pages for open
slots. Hebrew/RTL frontend. Live Supabase project: `ekugfzrmitvoiamevtfa`.

## Environment

- Python venv lives at the **repo root**: `venv/`. Backend commands run from `backend/`
  and reference it as `../venv/bin/...`.
- `.env` is at the **repo root** (not `backend/`) — shared by the backend (`app/config.py`
  reads `parents[2]/.env`), the Supabase CLI, and the frontend. It holds live secrets; it
  is gitignored.
- Frontend is **buildless** — vanilla JS ES modules + Tailwind CDN. No `package.json`, no
  bundler. Served as static files.

## Commands (run from `backend/` unless noted)

```bash
# Run the API
../venv/bin/uvicorn app.main:app --port 8000
# (fastapi entrypoint is configured in pyproject: `fastapi dev` also works if fastapi-cli installed)

# Tests (Supabase/agents are mocked — no network)
../venv/bin/python -m pytest tests/ -q
../venv/bin/python -m pytest tests/test_routers.py::test_lock_success -q   # single test
../venv/bin/python -m pytest tests/ -q --cov=app --cov-report=term-missing # coverage (gate: 90%)

# Quality gates (mypy is scoped to app/ only via pyproject `files=["app"]`)
../venv/bin/python -m mypy --strict
../venv/bin/ruff check app tests scripts
../venv/bin/black app tests scripts

# Agents (CLI runners — these hit live Google/OpenAI/Supabase and cost money)
../venv/bin/python -m scripts.run_discovery --lat 32.0853 --lng 34.7818 --radius 5000
../venv/bin/python -m scripts.run_national_discovery --cities haifa,eilat   # subset; omit for full 8-city sweep
../venv/bin/python -m scripts.run_scraping --loop --interval 120
```

```bash
# Frontend (from repo root) — serve the static consumer app
cd frontend/consumer && python3 -m http.server 3001    # then open http://localhost:3001
# Barber dashboard needs ?shop=<uuid>: frontend/dashboard, open with ?shop=...

# E2E (from repo root) — Playwright auto-starts backend:8000 + frontend:3001 via conftest
venv/bin/python -m pytest frontend/consumer/e2e -q
```

## Architecture — the non-obvious parts

**Three-agent "message board".** Discovery, Scraping, and (stub) Booking agents
(`backend/app/agents/`) read/write Supabase; the API serves the same tables. They share
data only through Postgres — there is no in-process coupling.

**Two Supabase client roles** (`backend/app/supabase_client.py`): `get_supabase()` (anon
key, RLS-enforced — used by all API request handlers) vs `supabase_admin` /
`get_supabase_admin()` (service-role key, **bypasses RLS** — agents only, never exposed to
clients). All `.execute().data` payloads go through the `one_row()` / `all_rows()` helpers
so the loosely-typed SDK response is normalised before use.

**Booking safety is in the database, not the app.** Pessimistic locking is implemented as
atomic SQL RPCs (`lock_slot` / `release_slot` / `confirm_booking` / `cancel_booking` in
`supabase/migrations/`). `backend/app/services/locking.py` is a thin wrapper around those
RPCs. Never reimplement locking logic in Python — change the RPC. Lock TTL is 300s
(`config.slot_lock_ttl_seconds`).

**Migrations** live in `supabase/migrations/` and are applied to the live project via the
Supabase MCP tools / CLI (not by the app at runtime). When you add a column, you must
update: the migration, the relevant RPC's `RETURNS TABLE`, the Pydantic model in
`app/models/schemas.py`, AND any test mock that returns partial rows (response_model
validation will reject missing required fields).

**Request path conventions** (`backend/app/routers/`): one router per resource with
`APIRouter(prefix=..., tags=...)`; `Annotated[...]` for all query params (no `Query(...)`
Ellipsis); a `response_model` on every endpoint that returns data (this is what filters
out fields like `user_token` from `/bookings`). Sync `def` routes are correct here — they
call the **sync** Supabase client and FastAPI runs them in a threadpool; only
`/admin/scraping/run` is `async` (awaits the agent). Admin router is mounted **only when
`environment != "production"`** (it triggers billed work).

**Frontend.** Consumer app (`frontend/consumer/`) is a hash-router SPA in vanilla JS
(`js/app.js` is the orchestrator; `js/booking.js` runs the lock→countdown→confirm flow;
`js/state.js` holds a per-browser `torli_user_token` in localStorage that scopes all
bookings/reviews). `frontend/stitch/` holds the design reference mockups the UI targets.
Dashboard (`frontend/dashboard/`) is a separate buildless React-via-CDN app.

## Testing notes

- Unit tests mock Supabase (`MagicMock` / patched `get_supabase`) — they never touch the
  network. `tests/test_*_integration.py` hit a **running** backend and auto-skip when
  `localhost:8000` is down.
- The E2E suite uses Page Objects (`frontend/consumer/e2e/pages.py`), web-first waits (no
  `wait_for_timeout`), a fixed `torli_user_token`, and saves a Playwright trace + screenshot
  to `e2e/artifacts/` only on failure. Quick-book / booking flows need **upcoming free
  slots** in the DB to exercise fully.
- `pyproject.toml` enforces branch coverage `fail_under=90`.

## Known intentional gaps (don't "fix" without checking `specs/torli_reverse_spec.md`)

- Booking Agent `submit()` is a **stub** (returns success without a real reservation).
- `GET /slots` is not time-filtered (returns past-dated free slots by design);
  `GET /slots/nearby` is the future-only one.
- Auth is not wired — the consumer uses an anonymous `user_token`; the owner-scoped RLS
  policies for the barber/dashboard side (`users`/`services`/`staff`/`appointments`) exist
  in migrations but `auth.uid()` is not yet supplied.
