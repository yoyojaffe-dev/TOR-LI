# Auth Layer — Operations & Twilio OTP (branch `feature/auth-layer`)

Working notes for stabilizing the Supabase + Twilio phone-OTP integration. Companion to the
[Authentication](README.md#authentication) section in the main README.

**Where credentials live:** the Twilio Account SID / Auth Token / Messaging Service SID are set in
the **Supabase dashboard**, never in this repo's `.env`. GoTrue (Supabase Auth) calls Twilio for us;
the backend only proxies `sign_in_with_otp` / `verify_otp`. So "stabilizing OTP" = getting the
Supabase Auth → Twilio link right, not changing backend code.

---

## 1. Twilio Messaging Service SID

A **Messaging Service** is a Twilio sender pool. Supabase sends OTP SMS through it.

**In Twilio Console:**
1. **Messaging → Services → Create Messaging Service** (name e.g. `tor-li-otp`, use-case "Verify/OTP").
2. Add a sender to its **Sender Pool** — your purchased phone number (or an Alphanumeric Sender ID
   where supported).
3. Copy the **Messaging Service SID** — starts with `MG…`.
4. Also have ready: **Account SID** (`AC…`) and **Auth Token** from the Console dashboard.

**In Supabase Dashboard → Authentication → Sign In / Providers → Phone:**
1. **Enable** the Phone provider and **enable phone signups**.
2. SMS provider = **Twilio**.
3. Fill: **Account SID** (`AC…`), **Auth Token**, and **Message Service SID** (`MG…`).
   - Prefer the Messaging Service SID over a single "From" number — it handles sender selection,
     compliance, and failover.
4. **Save.**

Sanity: an unconfigured/disabled provider makes `POST /auth/send-otp` return **503** (`could not
send code`); a misconfigured Twilio credential surfaces as **400/503** with GoTrue's error in the
backend log.

---

## 2. Test Phone Number (the testing "backdoor")

Supabase Auth lets you register **fixed phone→code pairs** that bypass Twilio entirely. GoTrue
returns the OTP as valid **without sending a real SMS**. Essential while the Twilio account is on a
**trial** (trial accounts can only text *verified* numbers and prepend a trial banner) and to avoid
per-SMS cost during development.

**Dashboard:** Authentication → Sign In / Providers → **Phone → "Test phone numbers"** (a.k.a. test
OTPs). Add entries such as:

| Phone (E.164) | Code |
|---|---|
| `+972500000000` | `123456` |
| `+972500000001` | `654321` |

Then in the app, log in with that phone and type the fixed code — no SMS leaves Twilio.

**Local Supabase (`supabase/config.toml`)** equivalent, if running the stack locally:
```toml
[auth.sms.test_otp]
"+972500000000" = "123456"
```

> ⚠️ **Security:** test numbers are a real auth backdoor. Use only non-production phone values, and
> **remove every test entry before going live** so no fixed code can mint a real session.

---

## 3. "Address already in use" — port troubleshooting (Makefile)

`uvicorn` on `:8000` or `python -m http.server` on `:3001` fails with `[Errno 48] Address already in
use` when a previous run (often an orphaned `--reload` worker or a backgrounded `&` process) still
holds the port.

**Fix — free both dev ports via the Makefile:**
```bash
make kill-ports        # frees :8000 and :3001
make backend           # restart FastAPI (:8000, --reload)
make frontend          # restart consumer SPA (:3001)
# or in one shot:
make dev               # kill-ports, then backend
```

`make kill-ports` runs `lsof -ti tcp:8000 | xargs kill -9` for each port (override with
`make kill-ports BACKEND_PORT=8001`). Manual equivalent if you prefer:
```bash
lsof -ti tcp:8000 | xargs kill -9
lsof -ti tcp:3001 | xargs kill -9
```

If a port is genuinely needed elsewhere, run the backend on another port and point the frontend at
it: `make backend BACKEND_PORT=8001` and set `window.__TORLI_BACKEND_URL__ = "http://localhost:8001"`
(consumer `config.js` reads that override before defaulting to `:8000`).

---

## 4. Final live verification (after the Twilio account is upgraded)

Upgrading from trial → paid removes the verified-numbers-only restriction and the trial banner, so
you can OTP **any** real phone. Verify the real Twilio path end-to-end:

1. **Remove the test phone numbers** (Section 2) so you exercise the actual Twilio send, not the
   backdoor.
2. Confirm the breaking migration is live (run once against the project):
   ```sql
   select proname, proargnames from pg_proc where proname = 'lock_slot';
   -- expect {p_slot_id, p_ttl_seconds} — NO p_user
   ```
3. Start the stack on clean ports:
   ```bash
   make kill-ports
   make backend      # terminal 1
   make frontend     # terminal 2
   ```
4. `curl -s localhost:8000/health` → `{"status":"ok", ...}`.
5. In the browser (`http://localhost:3001`), tap a slot → the RTL OTP modal → enter a **real**
   phone → a real SMS should arrive → enter the code.
6. **Watch the backend log** for the happy path:
   ```
   POST /auth/send-otp   -> 200
   POST /auth/verify-otp -> 200
   POST /bookings/lock   -> 200      # authed booking works
   ```
7. **Twilio Console → Monitor → Logs → Messaging** — confirm the message shows **delivered** (not
   `undelivered`/`failed`). Watch for trial-leftovers, unverified-number errors (error `21608`), or
   region/geo-permission blocks (error `21408`).
8. **DB check:** the new `public.bookings` row's `user_token` column holds the **`auth.users.id` UUID**
   of the logged-in user — proof bookings are scoped by `auth.uid()`, not the old browser token.

Negative check (no session → rejected at the API, before the DB):
```bash
curl -i -X POST localhost:8000/bookings/lock -H 'Content-Type: application/json' -d '{"slot_id":"x"}'
# HTTP/1.1 401 Unauthorized   {"detail":"missing bearer token"}
```

If send-otp 200 but no SMS: it's Twilio-side (sender pool empty, number not SMS-capable, geo
permissions, or still trial) — check the Twilio Messaging logs, not the backend.
