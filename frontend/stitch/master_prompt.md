# Tor — Master Stitch Prompt

Paste this whole document into Google Stitch as the project brief. It specifies the entire
product — both apps, every screen, every button transition, every feature — in RTL Hebrew.
If Stitch limits length, paste **Section 0 (Design System)** first, then one screen block at a time.

═══════════════════════════════════════════════════════════════════════
SECTION 0 — GLOBAL DESIGN SYSTEM (always apply)
═══════════════════════════════════════════════════════════════════════

Product: "Tor" (תור) — a barber-booking aggregator. Two apps in one project:
(A) a consumer mobile app to find & book a haircut, and (B) a barber/shop management dashboard.

Language & direction: ALL interface text is Hebrew, layout is RTL (right-to-left).
Numbers, times, prices and phone numbers read left-to-right inside the RTL layout.
Mobile frame: 430×932 (iPhone-class).

Visual language: modern, sleek, premium, minimal. DARK-FIRST.
- Canvas background #09090B (near-black). Card surfaces step up: #101012, #131214, #18171A, #202023.
- Borders are hairlines: rgba(255,255,255,0.06–0.10).
- ONE accent color: gold #EFB200 — used sparingly for the single most important thing on a
  screen (active nav tab, price, rating star, primary CTA, selected state). Never as wallpaper.
- Highest-emphasis button = solid WHITE (#FFFFFF) with black text (e.g. "ניווט", "שלם").
- Gold button = affirmative/brand action (e.g. "הזמן"). Dark button = secondary. Gold-tint
  outline = tertiary/repeat ("הזמן שוב").
- Text: primary #FAFAF9, secondary #A1A1AA, muted #71717A.
- Status colors: success green #34C759, danger/no-show red #FF453A, info blue #0A84FF.

Typography: one family for everything — Heebo (Hebrew+Latin), weights 400–900. Headings heavy
(800–900) and slightly tight. Body 400–500. Times, prices, countdowns and IDs in a monospace
with tabular figures (JetBrains Mono).

Shape & motion: cards radius 20px; buttons/inputs 16px; chips, toggles & avatars full pill.
Soft near-black drop shadows. The ONE live/next-up card gets a gold hairline ring + soft gold
glow. Bottom navigation is a translucent blurred bar; the active tab is gold. Press feedback =
quick scale to 0.97 (≈120ms). Screen transitions slide+fade (≈200ms, ease-out); pushing into a
detail slides in from the side, sheets/modals slide up from the bottom. Respect reduced-motion.

Imagery: warm, moody barbershop photos; barber portraits in black & white. Rounded containers
with a bottom protection gradient behind any overlaid text. No emoji in UI chrome.

Theme toggle: support a light theme too (warm cream canvas #FAF8F4, white cards, same gold).

═══════════════════════════════════════════════════════════════════════
SECTION A — CONSUMER APP
═══════════════════════════════════════════════════════════════════════

Bottom navigation (fixed, 3 items): בית (home) · פרופיל (profile) · EN (language flag toggle).
Active item gold. Tapping EN flips Hebrew⇄English.

────────────────────────────────────────
A1. HOME / DISCOVERY  (tab: בית)
────────────────────────────────────────
Layout top→bottom:
- Header: user avatar (right), and current location with a gold pin + "מיקום נוכחי" label.
  The app requests geolocation on load; while locating show "מאתר מיקום...". If granted,
  center everything on the user; if denied, default to תל אביב.
- Search row: a filter (funnel) button + a search field "חפש ספרים, שירותים...".
- Segmented toggle: רשימה (list) / מפה (map).
- LIST mode shows three horizontally-scrolling sections, each with a bold title and a gold
  "ראה הכל" (see all) link:
  • "זמינים בקרבתך" (available near you) — barber cards: shop photo + bottom gradient, a
    "4.9 ★" glass rating chip in the corner, a B&W round avatar with gold ring, name, shop,
    and a row of monospace available time-slot pills.
  • "דילים של הרגע האחרון" (last-minute deals) — compact rows: avatar, name, rating, specialty,
    distance, a gold price + lightning icon.
  • "בעלי הדירוג הגבוה" (top rated) — round avatars sorted by rating, name, rating, review count.

INTERACTIONS:
- Tapping any barber → push to A2 (barber profile).
- Tapping a time-slot pill on a card → ask first: a confirm dialog "לקבוע תור ל-HH:MM?"
  (book at this time?) — only on confirm proceed to booking; do NOT jump straight into the profile.
- "ראה הכל" on a section → full-screen list of ALL barbers for that category, with a back
  chevron and the section title; each row tappable to the profile. "דילים" rows show price + ⚡.
- MAP mode: a real dark-tiled map filling the area from the toggles down to the bottom nav.
  Each barber is a gold circular avatar pin; the user is a pulsing blue dot ("המיקום שלי").
  Tapping a pin shows a bottom card with the barber + a one-line travel row: walking 🚶, bike 🚲,
  car 🚗, transit 🚌 — each with the estimated time from the user's location, plus distance in
  km/m and a gold "הזמן תור" button. Tapping the card → barber profile.

FILTER FLOW (the funnel button):
- Opens a compact panel at the top titled "מה אתה מחפש?" with 4 small icon tiles in one row:
  סוג (type) · תקציב (budget) · מתי (when) · דירוג (rating). Home content stays visible & scrollable below.
- Tapping a tile drills into its options, with an "אישור" back button:
  • סוג תספורת: list — הכל, פייד, זקן, קליעות, ילדים, צבע.
  • תקציב: a SLIDER from ₪0 to the highest price (like clothing stores), pick a max.
  • מתי: a week of day options (היום, מחר, then weekdays) PLUS a "מועד מיוחד" button that opens
    a full calendar to pick any date.
  • דירוג: a SLIDER (same style as budget) for minimum rating, e.g. 0★→5★.
- A selected tile turns gold and shows its value. A gold "הצג N תוצאות" button (count updates live)
  sits directly under the tiles. Applying shows a filtered results list (cards) with active-filter
  chips at top and a list/map toggle. A "נקה" clears all.

────────────────────────────────────────
A2. BARBER PROFILE / PORTFOLIO
────────────────────────────────────────
- Full-width hero shop photo fading into the canvas; back chevron + share + heart (favorite)
  buttons floating on top (RTL: back on the right). Heart toggles filled red.
- Large B&W round avatar with gold ring overlapping the hero; name + shop; row of rating,
  review count, distance with pin; a short bio line.
- Two outline quick actions: "התקשר" (call) and "אינסטגרם".
- Tabs: תיק עבודות (portfolio) / חוות דעת (reviews) / שירותים (services).
  • Portfolio = 3-column Instagram-style photo grid.
  • Reviews = cards: author, date, 5-star row (filled gold), text.
  • Services = list rows: scissor icon, name, duration, price in gold; tapping expands.
- Sticky bottom gold CTA "הזמן תור עכשיו" on a blurred bar.

INTERACTIONS:
- Share button → bottom sheet "שתף עם חברים" with options: WhatsApp, Instagram, Facebook, SMS.
- "הזמן תור עכשיו" → push to A3 (booking).

────────────────────────────────────────
A3. REAL-TIME BOOKING
────────────────────────────────────────
- Header: back chevron, "הזמנת תור", barber name + avatar.
- "בחר שירות": horizontal service cards (name, duration, price); selected has gold tint + ring.
- Month calendar with ‹ › month nav; available days normal, unavailable dimmed, selected = solid gold.
- A small gold pill "מסונכרן בזמן אמת עם לוח הזמנים" (synced live with the barber's system).
- After a day is picked: a row of time-slot pills (monospace). Taken slots are dashed +
  struck-through + disabled; selected = solid gold. Different days show different availability.
- Sticky bottom: service name + price summary and a gold confirm button
  "אישור HH:MM · ₪NN" (disabled until date+slot chosen). Booking the slot "claims" it.
- Confirm → push to A4 (checkout).

────────────────────────────────────────
A4. CHECKOUT & PAYMENT
────────────────────────────────────────
- Header: back chevron, "אישור ותשלום".
- Order summary card: barber, service + price, date + time, bold total in gold.
- "אמצעי תשלום": selectable rows — Apple Pay, כרטיס אשראי (credit card), Visa ····4242.
  Selected row gold-tinted with a gold check.
- A red-tinted warning banner with a triangle icon: "מדיניות ביטול ואי-הגעה" — cancel up to
  2h before free; no-show or late cancel = ₪40 charge.
- A "תשלום מאובטח · מוצפן SSL" line with a shield icon.
- Sticky bottom: an agree checkbox ("אני מסכים/ה לתנאי השימוש ומדיניות הביטול") and a WHITE CTA
  "שלם ₪NN · אשר תור" (disabled until agreed). Tapping shows "מעבד תשלום..." then a success state.
- SUCCESS screen: big gold check, "שריינת!", "נתראה אצל {barber} ב-HH:MM", a live/glow summary
  card with service/date/time, and a gold "חזרה לדף הבית".

────────────────────────────────────────
A5. MY BOOKINGS / DASHBOARD  (tab: פרופיל)
────────────────────────────────────────
- Centered title "ההזמנות שלי" + subtitle. Tabs: הזמנות / מועדפים / חשבון.

הזמנות (bookings):
- "קרובים": ONE highlighted upcoming card with gold ring + glow, a gold countdown badge
  "מתחיל בעוד 2 שע׳ 45 דק׳", barber avatar, service, date/time, and two buttons:
  WHITE "ניווט" + dark "שינוי תור".
- "ניווט" → bottom sheet "מעולה! איך אתה מתכנן להגיע?" with three modes:
  ברגל (→ Google Maps / Apple Maps), באוטו (→ Google Maps / Waze), תחב״צ (→ Moovit / Google Maps).
  Picking a mode lists the apps; tapping one deep-links to that app with navigation to the barber.
- "תורים קודמים": flat rows (service, barber, date) with a gold-outline "הזמן שוב" button that
  jumps straight to that barber's profile. Each past booking also lets you rate & review
  (stars + text) the haircut and the barber.

מועדפים (favorites): saved barber cards (avatar, name, rating, shop, slots), tappable to profile,
with a filled red heart.

חשבון (account): user avatar + name + city; an option to CHANGE the profile photo (choose from
gallery OR take a new photo). Menu rows: אמצעי תשלום (Apple Pay / כרטיס אשראי / Visa),
הזמנות שמורות, הגדרות (language, notifications, privacy). A red "התנתק" (log out).

═══════════════════════════════════════════════════════════════════════
SECTION B — BARBER / SHOP DASHBOARD
═══════════════════════════════════════════════════════════════════════

Header: shop avatar, screen title, shop name. Bottom nav (5 tabs):
לוח שנה (calendar) · סטטיסטיקות (stats) · עובדים (staff) · שירותים (services) · הגדרות (settings).
All five share live state: changing staff/services updates the calendar, stats and forms everywhere.

────────────────────────────────────────
B1. לוח שנה — CALENDAR / APPOINTMENTS
────────────────────────────────────────
- Row of round staff avatars to filter by barber (first = "הכל"/all). Toggling a staff member
  off elsewhere removes them here.
- Horizontal week-day picker; selected day solid gold. Each day shows DIFFERENT appointments.
- Three summary tiles: תורים (count) · הושלמו (completed) · הכנסות (revenue ₪).
- A dashed gold "+ הכנס תור חדש" button → modal form to manually book a client:
  שם הלקוח, טלפון, שירות (select), ספר (select active staff), שעה (time). Saving inserts the
  appointment into that day (sorted by time) and updates the stats.
- Time-ordered appointment cards, color-coded by status: completed = gold tint, upcoming = blue
  tint, pending = red tint, break ("הפסקה") = neutral. Each: "service - client", time · duration
  · price, phone, a status pill (הושלם / קרוב / ממתין), and which barber.

────────────────────────────────────────
B2. סטטיסטיקות — STATISTICS
────────────────────────────────────────
- Staff-avatar filter row: pick one barber for HIS personal stats, or "כל הצוות" for all.
- Revenue card: big monospace ₪ figure + green area line chart.
- Visits card ("מספר פגישות"): big number + blue line chart + a time-period segmented control
  1M / 3M / 6M / 1Y / All — EACH period shows different numbers and a different trend.
- Status donut (הושלמו / קרובים / ממתינים) with a % legend.
- A 2-column grid of stat tiles (תורים, הכנסה + average, ספרים פעילים, שיעור השלמה).

────────────────────────────────────────
B3. עובדים — STAFF MANAGEMENT
────────────────────────────────────────
- List rows: B&W avatar, name, role, a gold active on/off toggle, and edit ✏️ + delete 🗑️.
- Toggle off → that barber disappears from the calendar & stats filters (their appointments stay).
- Edit → inline name/role fields with save/cancel. Delete → centered confirm modal.
- Floating gold "+" → add-employee form (name, role). Every action must really update state
  and propagate to the other tabs.

────────────────────────────────────────
B4. שירותים — SERVICES & PRICING
────────────────────────────────────────
- Service cards: icon, name, description, gold price (monospace), duration, monthly bookings count.
- Each card has edit + delete. Edit expands inline with an emoji/icon picker + name, description,
  price, duration fields. A dashed "+ הוסף שירות" adds one. Delete asks to confirm.
- The services list feeds the "שירות" select in the calendar's add-appointment form.

────────────────────────────────────────
B5. הגדרות — SETTINGS
────────────────────────────────────────
- A list of rows, each icon + label + sublabel + chevron: פרטי העסק (business details),
  תשלומים (Apple Pay / כרטיס אשראי / Visa), התראות (notifications), חיבור אפליקציות,
  פרטיות ואבטחה, שפה (עברית/English), עיצוב (כהה/בהיר theme), עזרה ותמיכה.
- Tapping a row opens its working detail panel:
  • פרטי העסק: text fields (name, address, hours) + Save (shows a "נשמר ✓" toast).
  • התראות: labelled gold toggles (SMS, Push, דוא״ל, תזכורת אוטומטית).
  • שפה: עברית / English options. עיצוב: כהה / בהיר (actually switches the theme).
- Everything must function (toggles persist, saves confirm, language/theme apply).

═══════════════════════════════════════════════════════════════════════
DELIVERABLE
═══════════════════════════════════════════════════════════════════════
Generate every screen above as connected, tappable flows (not isolated mockups), fully RTL
Hebrew, dark theme with the gold accent, with the exact button hierarchy (white > gold > dark >
outline), the live/glow treatment on the one next-up card, the blurred bottom navs, and all the
modals/sheets/confirm dialogs described. Keep the consumer app and the barber dashboard as two
separate navigable apps inside the project.
```
