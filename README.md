# Tor-li

Real-time, location-based mobile web marketplace for booking last-minute haircuts.

Users see haircut slots available **right now** within their GPS radius, and book
in a couple taps. Behind the scenes, three autonomous agents keep the marketplace
fresh and complete bookings on the barbers' own websites.

## Architecture

```
frontend/            Static UI (Stitch-generated) + JS
├── consumer/        Vanilla-JS consumer app (discovery, map, realtime, booking)
└── dashboard/       React (buildless) management dashboard

backend/             FastAPI service + 3 agents
├── app/
│   ├── main.py          FastAPI app, CORS, /health, agent lifespan hooks
│   ├── config.py        Settings from repo-root .env
│   ├── supabase_client.py
│   ├── models/          Pydantic schemas
│   ├── routers/         barbershops (radius), slots, bookings (lock/confirm)
│   ├── services/        locking (pessimistic lock via RPC)
│   └── agents/          discovery / scraping / booking  (SKELETONS)

supabase/migrations/ PostGIS schema, radius + locking RPCs, RLS, realtime
```

**Stack:** FastAPI (Python) · Supabase (Postgres + PostGIS + Realtime) ·
Playwright · OpenAI · Google Maps Places · Twilio · Railway.

### The three agents (message board = Supabase)
- **Discovery** — scheduled; Google Maps Places → `barbershops`.
- **Scraping** — loop worker; Playwright scrapes booking pages → OpenAI parses HTML → `available_slots`.
- **Booking** — on-demand; Playwright submits the reservation on the barber's site.

> Foundation phase: agents are skeletons (signatures + Supabase contracts + TODOs).
> Real Playwright/OpenAI automation lands in the next phase.

### Key workflows
- **Realtime sync** — frontend subscribes to `available_slots` changes.
- **Pessimistic locking** — `lock_slot` RPC holds a ~90s lock while the user pays; double-booking impossible.
- **Radius search** — `barbershops_within_radius` RPC (PostGIS `ST_DWithin`, GiST-indexed).

## Run locally

```bash
# Backend
cd backend
python3 -m venv ../venv && ../venv/bin/pip install -r requirements.txt
../venv/bin/uvicorn app.main:app --reload   # http://localhost:8000  (/health, /docs)
../venv/bin/pytest                           # smoke tests

# Frontend (static)
cd frontend/consumer && python3 -m http.server 5173   # http://localhost:5173
```

Secrets live in the gitignored repo-root `.env` (see `backend/.env.example`).

## Frontend ↔ Stitch
The UI is designed in the Stitch "TOR LI" project. The repo ships thin `index.html`
shells with the DOM hooks the JS drives (`#map`, `#barbershop-list`, `#slot-list`,
`#lock-timer`, `#booking-form`; dashboard mounts at `#root`). Paste the Stitch
markup/styles into those shells, keeping the hook ids — no CSS is authored here.

## Deploy (Railway)
`backend/Procfile` + `backend/railway.json` (set the service root directory to
`backend`). Configure the same env vars from `.env.example` in Railway.
