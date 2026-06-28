# Tor-li - Future Growth Roadmap

Technical plans for the next wave of features on top of the MVP
(`feature/barber-dashboard-mvp`). Each item lists the goal, data model, frontend/backend
touchpoints, and a rough effort estimate. The guiding constraints stay the same: **buildless**
frontends, **Supabase** as the shared backbone, consumer is **anonymous (`torli_user_token`)**,
barber is **authenticated (Supabase Auth + owner RLS)**.

---

## 1. WhatsApp Quick-Chat
**Goal:** one-tap WhatsApp conversation between a customer and a shop (e.g. "running 5 min late",
"can I move my 16:00?") without building a chat system.

- **Data model:** none new. Uses existing `barbershops.phone` (shop) and `bookings.customer_phone`
  (client). Add a small phone normalizer to E.164 (Israel `0XX` -> `+9725XX`).
- **Frontend (consumer):** a "WhatsApp" action on the barber profile + booking-success screen ->
  `https://wa.me/<intlPhone>?text=<urlencoded prefilled message>` (shop name + slot time).
- **Frontend (dashboard):** on each Calendar appointment card, a WhatsApp icon -> `wa.me` to the
  client's number with a prefilled greeting.
- **Backend:** none.
- **Effort:** **S** (half to one day). Main work is the phone-normalization helper + buttons.
- **Risks:** invalid/missing numbers -> hide the action when phone is absent.

## 2. Availability Overrides
**Goal:** let a barber block time, mark a day off, or set custom hours that override the default
weekly `opening_hours` - reflected in what customers can book.

- **Data model:** new table `availability_overrides`
  (`id`, `barbershop_id` -> shops, `staff_id` nullable -> staff, `date`, `kind`
  `'closed' | 'custom'`, `open_time`, `close_time`, `note`, `created_at`). Owner-scoped RLS via the
  existing `is_shop_owner(barbershop_id)` predicate; public-read so the consumer can respect it.
- **Backend / DB:** an override should suppress/adjust `available_slots` for that date. Options:
  (a) a generation step that skips slots inside a `closed` override, or (b) a `slots_visible` view /
  RPC that filters slots against overrides at read time (preferred - no destructive slot edits).
  The consumer `GET /slots*` and `slots/nearby` join against this.
- **Frontend (dashboard):** an availability editor in Calendar/Settings - tap a day -> mark closed
  or set custom hours; list/delete overrides. Reuse the shared `ConfirmModal`.
- **Effort:** **M** (2-4 days). Migration + read-time filtering + editor UI.
- **Risks:** interaction with already-booked slots inside a newly-closed window - surface a warning,
  do not auto-cancel.

## 3. New Appointment Alerts
**Goal:** the barber is notified the moment a customer books - no manual refresh.

- **Data model:** none required (optional `bookings.seen_by_owner` boolean to compute an unseen
  badge that persists across reloads).
- **Frontend (dashboard):** the realtime subscription on `bookings` already triggers `reload()`.
  Layer on: an in-app **toast + sound** on a new INSERT, an **unseen-count badge** on the Calendar
  nav tab, and an optional **Web Notifications API** prompt (`Notification.requestPermission()`) for
  OS-level alerts when the tab is backgrounded.
- **Backend:** none for in-app. (Future: Supabase Edge Function + push/SMS for offline barbers.)
- **Effort:** **S-M** (1-2 days). Diff the realtime payload to detect new vs. updated rows; manage
  unseen state; permission UX.
- **Risks:** autoplay-blocked sound (gate behind a user gesture); notification-permission fatigue.

## 4. Client Loyalty View
**Goal:** show the barber their repeat customers - visit count, last visit, lifetime spend - to
power retention (e.g. "10th cut free").

- **Data model:** derive from existing `bookings` (`customer_phone`, `customer_name`, joined slot
  `price`/`slot_time`) grouped per shop. Start as a **read-time aggregation** (Postgres RPC
  `client_loyalty(shop)` or a `group by customer_phone` query under owner RLS). Later, a materialized
  `clients` rollup table if volume grows.
- **Frontend (dashboard):** a new "My Clients" section/tab - sortable list (most visits / most
  recent / top spenders), each row -> visit history + the WhatsApp action from feature #1.
- **Backend:** an owner-scoped aggregate RPC (SECURITY DEFINER, filtered by `is_shop_owner`) or a
  direct grouped select if RLS performance is fine.
- **Effort:** **M** (2-3 days). Aggregation + list/detail UI.
- **Risks:** phone numbers are the identity key - normalize consistently (shared with feature #1) so
  the same client is not split across formats.

---

## Suggested sequencing
1. **WhatsApp Quick-Chat** (small, high value, unblocks the loyalty action).
2. **New Appointment Alerts** (small, big perceived quality bump; realtime already exists).
3. **Client Loyalty View** (reuses phone normalization + WhatsApp).
4. **Availability Overrides** (largest - touches the slot read path on both apps).

## Cross-cutting prerequisites
- A shared **E.164 phone normalizer** (used by WhatsApp + Loyalty).
- Keep new owner reads behind **owner RLS** (mirror `owner_read_bookings`); never expose the service
  role to the browser.
- Record every schema change as a file in `supabase/migrations/` and apply via the Supabase MCP/CLI.
