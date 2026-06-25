# Tor — Stitch Handoff Pack

This folder is a hand-off of the **Tor** barber-booking product (consumer app + barber
dashboard) for rebuilding / iterating inside **Google Stitch**.

Stitch ingests **images** + a **text prompt**. For each screen below: upload the matching
PNG and paste the prompt. Start every Stitch session with the **Design system** block so
the visual language stays consistent.

---

## Design system (paste first / keep in the system prompt)

```
Design language: modern, sleek, premium barber-booking app. Dark-first.
Direction: RTL Hebrew primary (all UI text in Hebrew), numerals left-to-right.

Colors:
- Canvas background: #09090B (near-black)
- Card surfaces: #101012 → #131214 (subtle steps), hairline borders rgba(255,255,255,0.06–0.10)
- Single accent: gold #EFB200 (used sparingly — active tab, price, rating star, primary CTA)
- Highest-emphasis button: white #FFFFFF with black text
- Text: primary #FAFAF9, secondary #A1A1AA, muted #71717A
- Status: success #34C759, danger/no-show #FF453A, info #0A84FF

Type: one family for everything (Heebo, weights 400–900). Headings heavy (800–900),
slightly tight. Times/prices/countdowns in a monospace with tabular figures (e.g. JetBrains Mono).

Shape & feel: cards radius 20px, buttons/inputs 16px, chips & avatars full pill.
Soft near-black drop shadows. The ONE live/next-up card gets a gold hairline ring + soft gold glow.
Bottom nav is a blurred translucent bar; active tab is gold. Press = quick scale 0.97.
No gradients-as-wallpaper, no emoji in chrome. Imagery = warm moody barbershop photos,
barber portraits in black & white.
```

---

## Consumer app — `app/`

**01-home.png** — Home / Discovery
```
Build the home/discovery screen of a barber-booking app (RTL Hebrew, dark, gold accent).
Top: user avatar + current location with a gold pin. A search field with a filter (funnel)
button beside it. A segmented "list / map" toggle (רשימה / מפה). Horizontal carousel
"זמינים בקרבתך" (available near you) of barber cards — each card: shop photo with a bottom
gradient, a "4.9 ★" glass rating chip top-corner, round B&W barber avatar with gold ring,
name, shop, and a row of monospace time-slot pills. Below: "דילים של הרגע האחרון" (last-minute
deals) as compact rows with price in gold, and "בעלי הדירוג הגבוה" (top rated) avatars.
Fixed bottom nav: בית / פרופיל / EN, active tab gold.
```

**02-profile.png** — Barber Profile / Portfolio
```
Barber profile screen. Full-width hero shop photo fading into the dark canvas. Large B&W
round avatar with gold ring overlapping the hero, name + shop. Row of rating, review count,
distance. Two outline quick-action buttons (התקשר / אינסטגרם). Tabs: תיק עבודות (portfolio) /
חוות דעת (reviews) / שירותים (services). Portfolio = 3-column Instagram-style photo grid.
Sticky bottom gold CTA "הזמן תור עכשיו" (book now) on a blurred bar.
```

**03-booking.png** — Real-time Booking
```
Booking screen. Header with back chevron, "הזמנת תור", barber name + avatar. Horizontal
service selector cards (name, duration, price) — selected one has a gold tint + ring. A month
calendar grid; available days normal, unavailable dimmed, selected day = solid gold. A small
gold pill badge "מסונכרן בזמן אמת" (synced in real time). Below: available time-slot pills
(monospace) — taken ones dashed + struck-through, selected = solid gold. Sticky bottom summary
(service + price) and a gold confirm CTA.
```

**04-dashboard.png** — My Bookings (user)
```
User "my bookings" screen, centered title "ההזמנות שלי". Tabs הזמנות / מועדפים / חשבון.
Section "קרובים": ONE highlighted upcoming-booking card with a gold ring + glow, a gold
countdown badge ("מתחיל בעוד 2 שע׳ 45 דק׳"), barber avatar, service, date/time, and two
buttons — white "ניווט" (navigate) + dark "שינוי תור" (change). Section "תורים קודמים":
past bookings as flat rows with a gold-outline "הזמן שוב" (rebook) button.
```

---

## Barber dashboard — `dashboard/`

**01-calendar.png** — Calendar / Appointments
```
Barber shop management — daily calendar. Top: row of round staff avatars to filter by barber
(first = "all"). A horizontal week-day picker, selected day solid gold. Three summary stat
tiles (appointments / completed / revenue ₪). A dashed gold "+ הכנס תור חדש" (add appointment)
button. Then a time-ordered list of appointment cards color-coded by status: completed = gold
tint, upcoming = blue tint, pending = red tint, break = neutral. Each card: service - client,
time · duration · price, status pill. Bottom tab bar (calendar/stats/staff/services/settings).
```

**02-stats.png** — Statistics
```
Analytics screen for a barber shop. Staff-avatar filter row (select one barber for personal
stats, or "all"). A revenue card with a big monospace ₪ figure and a green area line chart.
A visits card with a blue line chart and a time-period segmented control (1M/3M/6M/1Y/All)
that changes the numbers. A status-breakdown donut chart (completed/upcoming/pending) with a
legend. A 2-column grid of stat tiles. Dark, gold accent, RTL Hebrew.
```

**03-employees.png** — Staff management
```
Staff management list. Each row: B&W round avatar, name, role, a gold on/off toggle (active),
and edit ✏️ + delete 🗑️ icon buttons. A floating gold "+" button to add an employee (opens a
form with name + role). Delete asks for confirmation in a centered modal. RTL Hebrew, dark.
```

**04-services.png** — Services & pricing
```
Services manager. List of service cards: icon, name, description, price in gold (monospace),
duration, and monthly bookings count, with edit + delete buttons. Editing expands inline with
an icon picker, name, description, price, duration fields. A dashed "+ הוסף שירות" add button.
RTL Hebrew, dark, gold accent.
```

**05-settings.png** — Settings
```
Settings screen — a list of rows (business details, payments, notifications, app connections,
privacy, language, theme, help), each with an icon, label, sub-label and a chevron. Tapping a
row opens its detail panel (e.g. notifications = labelled toggles; language = עברית/English
options; business details = text fields with a Save button). RTL Hebrew, dark, gold accent.
```

---

## Notes
- All screens are 430×932 (mobile, ~iPhone). Keep the fixed bottom nav on the main tabs.
- Screenshots are cropped to the device screen. They're references for layout + style — feed
  them as the image input and use the prompts to drive structure.
- Fonts in the screenshots are Heebo + JetBrains Mono (Google Fonts). If Stitch substitutes,
  pick a clean geometric Hebrew-capable sans + any tabular mono.
