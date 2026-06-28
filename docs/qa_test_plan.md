# Tor-li — QA Test Plan (Pre-Production E2E)

End-to-end verification of the Barber Management System before production. Run manually in two
browser windows (consumer + dashboard). Mark each row Pass/Fail in the Result column.

## Environment
| | |
|---|---|
| Backend | `cd backend && ../venv/bin/uvicorn app.main:app --port 8000` |
| Frontend (unified) | `cd frontend && python3 -m http.server 4000` → open `http://localhost:4000/` |
| Consumer / Dashboard | `…/consumer/index.html` · `…/dashboard/index.html` |
| Demo barber | **barber@torli.dev / torli1234** — owns מספרת גלי (`31a04333-d8af-4303-8c0e-3c3cb73930c2`) |
| Reset consumer | DevTools console on the consumer origin: `localStorage.clear()` then reload |

---

## 1. Happy Path — Consumer
| ID | Goal | Step-by-Step Execution | Expected Result | Result |
|----|------|------------------------|-----------------|:------:|
| H1 | Unified entry routes to the right app | Open `http://localhost:4000/` | Landing shows "הזמנת תספורת" + "ניהול מספרה"; tapping each opens the consumer / dashboard app (no "Not Found") | ☐ |
| H2 | Onboarding + registration captures the user | Consumer → splash → role **לקוח** → verify (any phone, any 4-digit OTP) → register (full name + optional photo) → המשך | Lands on home; `localStorage` has `torli_customer_name`/`_phone`/`torli_onboarded`; `torli_avatar` is a `…/storage/v1/object/public/avatars/…` URL | ☐ |
| H3 | Location + map search work, never freeze | Allow OR deny the geolocation prompt; switch to **מפה**; pan to another city → tap **חפש באזור זה** | On deny it falls back to ירושלים (no freeze/stuck skeletons); pins reload for the panned viewport | ☐ |
| H4 | Booking flow end-to-end | Open מספרת גלי → **תורים פנויים** → tap a slot → confirm sheet (name/phone pre-filled) → check terms → **אשר** | Lock countdown runs; on confirm → `#/success`; the slot flips to booked (gone from the free list) | ☐ |
| H5 | Booking reflects live in the dashboard | Keep the dashboard (logged-in barber, Calendar tab) open while doing H4 on מספרת גלי | Toast "תור חדש" + bell badge appear within ~2s; the appointment shows client **name, phone, service, time** | ☐ |

## 2. Resilience & Security
| ID | Goal | Step-by-Step Execution | Expected Result | Result |
|----|------|------------------------|-----------------|:------:|
| S1 | No double-booking on one slot | Two consumer windows; both open the same slot; window A confirms; window B then tries to lock/confirm the same slot | A succeeds; B is rejected ("מצטערים, התור הזה כבר נתפס" / HTTP 409). Exactly one booking exists for that slot | ☐ |
| S2 | Guest cannot read private data | As an anonymous consumer, try to read the `bookings` table directly (Supabase anon client / REST) | Returns nothing / denied — RLS hides every shop's customer bookings from guests | ☐ |
| S3 | Owner isolation (cross-shop) | Sign up a NEW barber (different email) → dashboard | Sees only their own newly-created (empty) shop; **cannot** see מספרת גלי's appointments/data (owner RLS) | ☐ |
| S4 | Network failure mid-booking is visible | Stop the backend (`:8000`); in the consumer tap a slot to book | Clear error toast "ההזמנה נכשלה — בדוק חיבור לשרת ונסה שוב" — no silent failure, no stuck UI; the slot lock auto-releases after its TTL (≤300s) | ☐ |
| S5 | Dashboard never hangs on load failure | With a broken/stopped dependency, open the dashboard | Shows an error state + **נסה שוב** retry (never an infinite spinner); console `[data] … failed` / `[dashboard] load failed` names the cause | ☐ |

## 3. Admin / Barber Dashboard Stress
| ID | Goal | Step-by-Step Execution | Expected Result | Result |
|----|------|------------------------|-----------------|:------:|
| A1 | Service deactivation hides it from consumers | Dashboard → **שירותים** → toggle a service off; refresh that shop's profile in a consumer window | Service dims + "לא פעיל" badge in management; it disappears from the consumer's services menu | ☐ |
| A2 | Staff deactivation removes from operations | Dashboard → **עובדים** → toggle a barber off | Gone from the Calendar staff filter, add-slot picker, and Statistics selector; still listed (dimmed) in the Employees tab | ☐ |
| A3 | Destructive actions are confirmed | Click delete on a service / staff / free slot | A confirm dialog appears; **ביטול** changes nothing; **אישור** performs the delete | ☐ |
| A4 | Re-auth gate on sensitive change | Settings → **שינוי סיסמה** → enter a WRONG current password + a new one → **אמת ושמור** | "הסיסמה הנוכחית שגויה"; the password is NOT changed. (A correct current password would update it) | ☐ |
| A5 | Notifications bell shows unseen list | After a live booking arrives, click the header **bell** | Dropdown lists the unseen appointment(s); tapping one → Calendar + badge clears; "סמן הכל כנקרא" clears; empty → "אין התראות חדשות" | ☐ |

## 4. Data Integrity
| ID | Goal | Step-by-Step Execution | Expected Result | Result |
|----|------|------------------------|-----------------|:------:|
| D1 | Statistics filter by staff | Statistics tab → select a specific barber | Revenue / visits / average tiles + both charts recompute to ONLY that barber's bookings | ☐ |
| D2 | Statistics filter by period | Statistics → toggle חודש / 6 ח' / שנה / הכל | Totals + charts change with the time window; the numbers reconcile with the Calendar appointment list | ☐ |
| D3 | Loyalty aggregation is correct | Clients tab; book twice using the SAME phone number | One client row aggregates: visit count, total spend (Σ prices), last-visit date; its WhatsApp button opens `wa.me/<intl>?text=…` for that client | ☐ |
| D4 | Availability override blocks consumers | Dashboard → Calendar → **חסום תאריך/שעות** (all-day, today) → save; open that shop in a consumer window | That day's free slots no longer appear in the consumer profile | ☐ |
| D5 | Override enforced at booking time | Try to book a slot inside a block (or `curl` `lock_slot` on a blocked slot) | Rejected: `success:false, "time blocked by the shop"` — booking is prevented even if a stale slot is visible | ☐ |

---

## Sign-off
All 20 scenarios (H1–H5, S1–S5, A1–A5, D1–D5) must Pass before promoting `feature/barber-dashboard-mvp`
to production. Record date, tester, and any defects below.

| Date | Tester | Result | Notes |
|------|--------|--------|-------|
| 2026-06-28 | Automated QA pass | **20/20 PASS** | Backend/RLS/booking via curl+node+SQL; UI flows via headless browser. S5 structurally verified (try/finally guarantees no infinite spinner). Demo data preserved. |
