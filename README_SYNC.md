# Booking Sync — `fix/deal-price-modal`

Notes on the post-booking sync behaviour added on this branch: how a booked
slot leaves the Consumer UI instantly and shows up on the Barber Dashboard
live, how to verify it locally, and what is still open.

## What this branch changes

1. **Deal price in the confirmation sheet** — the confirm sheet shows the
   discounted `deal_price` as the primary total (danger colour) with the
   original list price struck through; the CTA charges the deal price.
2. **Optimistic drop + refetch after booking** — a booked slot is removed from
   the Consumer list the moment the booking succeeds, then reconciled with the
   server. (This file.)
3. **Deal-price persistence** — migration
   `supabase/migrations/20260629150000_booking_snapshots_deal_price.sql`
   snapshots the effective (deal-aware) price onto the booking row server-side.
   **Not yet applied to the live project** — see Known Issues.

## Optimistic Drop logic

Location: `frontend/consumer/js/app.js` → `onConfirmBooking()`.

On a successful `confirm_booking`:

1. **Optimistic drop.** The just-booked slot id (`store.pendingSlot.id`) is
   filtered out of both cached feeds and the list is re-rendered immediately:

   ```js
   const bookedId = store.get().pendingSlot?.id;
   if (bookedId != null) {
     store.set({
       nearbySlots: (store.get().nearbySlots || []).filter((s) => s.slot_id !== bookedId),
       deals:       (store.get().deals       || []).filter((s) => s.slot_id !== bookedId),
     });
     renderNearbySlots(); // also re-renders the deals rail
   }
   ```

   This makes the screen accurate the instant the user returns from the success
   screen — no manual reload, no waiting on the network.

2. **Server reconcile.** A background `loadNearby()` refetches shops +
   `nearbySlots` + `deals` and re-renders, picking up anything else that
   changed. It is guarded so a refresh failure can never freeze the flow:

   ```js
   if (store.get().position) {
     loadNearby().catch((err) => console.warn("post-booking refresh failed:", err?.message));
   }
   ```

   The refetched feeds come from RPCs that filter `status = 'free'`, so the
   booked slot (now `status = 'booked'`) is excluded — the optimistic state and
   the server state agree.

### Why both steps

- Optimistic drop alone would drift from the server if anything else changed.
- Refetch alone has a visible lag (network round-trip) during which the booked
  slot still shows as available — the exact bug this fixes.

Together: instant correctness + eventual authority from the server.

## Dashboard side (already present, not added here)

The Barber Dashboard subscribes to Supabase Realtime and re-renders on any
change to its shop's slots/bookings:

- `frontend/dashboard/js/data.js` → `subscribeShop()` listens to
  `postgres_changes` on `available_slots` (filtered to the shop) and `bookings`.
- `frontend/dashboard/js/dashboard.js` wires it: `subscribeShop(shop.id, reload)`.

So a Consumer booking flips `available_slots.status` → the Dashboard's
subscription fires → `reload()` → the appointment appears with no refresh.

## Verify sync locally

Start three services (consumer + dashboard served from this branch):

```bash
# 1. Backend API (needs repo-root .env + venv)
cd backend && ../venv/bin/uvicorn app.main:app --reload --port 8000

# 2. Consumer
cd frontend/consumer && python3 -m http.server 3001    # http://localhost:3001

# 3. Dashboard
cd frontend/dashboard && python3 -m http.server 3002    # http://localhost:3002/index.html
```

Demo barber (owns מספרת גלי, the deal shop `31a04333-d8af-4303-8c0e-3c3cb73930c2`),
per `docs/qa_test_plan.md`:

- Dashboard login: `barber@torli.dev` / `torli1234`
- Consumer login: phone + SMS OTP (real number required)

Steps:

1. Dashboard: log in, park on the calendar/appointments view for מספרת גלי.
2. Consumer: open the 🔥 מבצע deal card → confirm sheet shows deal price
   (e.g. **₪10**) big/red with the original (**₪86**) struck → log in → confirm.
3. Watch, no refresh:
   - **Dashboard**: the appointment appears live (~1–2s); the slot flips
     free → booked.
   - **Consumer**: return home → the slot is gone from the list immediately.

### Automated render check

A headless Playwright check exercised the real `openConfirmSheet` and
`renderNearbySlots` (driven via the `window.__torli` debug hooks):

- Confirm sheet total rendered `₪10 ₪86 🔥 מבצע`; CTA `₪10`.
- Deals list `[AAA, BBB]` → after dropping `AAA` → `[BBB]`. No console errors.

## Known issues / future improvements

- **Migration not applied to prod.** `20260629150000_booking_snapshots_deal_price.sql`
  must be applied to the live project (`ekugfzrmitvoiamevtfa`) for booking
  history / dashboard to show the *charged* price. Until then those read the
  slot's list price. Apply via Supabase MCP/CLI before merge.
- **Realtime must be enabled** on `available_slots` and `bookings` (publication
  / replication) for the Dashboard live update. If the appointment only shows
  after a manual refresh, that is the cause.
- **`barber-signup` does not link a shop.** The dev endpoint creates an owner
  account but not shop ownership; a fresh account sees an empty dashboard
  (owner-scoped RLS). The demo account already owns מספרת גלי.
- **Debug hooks left in `window.__torli`** (`openConfirmSheet`,
  `renderNearbySlots`) for E2E/manual verification. Harmless; remove if not
  wanted in production.
- **Optimistic drop is keyed on `slot_id`.** If a feed item ever lacks
  `slot_id`, it would not be dropped — currently all slot feeds carry it.
- **Future:** drive the Consumer's own slot list off the same Supabase Realtime
  channel the Dashboard uses, so even slots booked by *other* users disappear
  live without a refetch.
