# יומן שינויים — 2026-06-30

רשומת סשן עבודה. מתעדת את כל מה שבוצע ב-30/06/2026 על פני כל הברנצ'ים.
מבוסס על `git log` בפועל ועל ה-diffs, לא מהזיכרון. אינו מחליף את `README.md`.

נקודות כניסה לפרודקשן:
- **Backend:** `https://tor-li-production.up.railway.app`
- **Frontend (סטטי):** `https://frontend-production-2c43.up.railway.app` — דף נחיתה
  המקשר ל-`/consumer/` ול-`/dashboard/`.

מיגרציות חדשות היום (`supabase/migrations/`):
- `20260630000000_deal_aware_booking_history.sql`
- `20260630010000_add_google_types.sql`
- `20260630020000_upsert_service_fill_price.sql`

---

## תשתית — Railway Production

**מה היה חסר:** האפליקציה לא הייתה פרוסה. הפרונט הוא buildless (vanilla JS,
ללא bundler) וה-backend הוא FastAPI — שניהם דרשו הגדרת פריסה מאפס ב-Railway.

**מה נעשה:**
- **Static-serve לפרונט** (`d066add`, ענף `feat/frontend-prod-config`): קונפיג
  Nixpacks + `python -m http.server`. שורש ההגשה מגיש דף launcher שמקשר
  ל-`./consumer/index.html` ול-`./dashboard/index.html`.
- **רזולוציית BACKEND_URL לפי הוסט** (`dd9b1b8`): הפרונט מזהה אוטומטית את כתובת
  ה-backend בפרודקשן לפי `window.location.hostname`. קובץ: `frontend/consumer/js/config.js`
  (`PROD_FRONTEND_HOST`, `PROD_BACKEND_URL`).
- מוזג ל-main: `6d1d07d`, `f96bbb2`, `e6bb4b7`, `75d0b69`.
- **Makefile לפיתוח** (`8d29ab9`): קיצורי run/serve/test/kill-ports.

**באג ה-deploy התקוע (תקלה אמיתית שאובחנה):**
- תיקון ה-hostname ב-`config.js` "לא נחת" בפרודקשן עד שמוזג בפועל ל-`main` —
  Railway פורס מ-`main`, ותיקונים שנשארו בענף לא הגיעו ל-live.
- **GitHub auto-deploy מ-`main`** משמעו שתיקונים מקומיים בלבד "מתבטלים" כשהפרודקשן
  מגיש מחדש מה-main הישן עד למיזוג. דרש משמעת מיזוג: כל תיקון פרודקשן חייב
  להגיע ל-`main`, לא להישאר בענף.
- אומת בסיום: `/health` → 200; הפרונט בפועל מגיש את הקוד החדש בנתיב הנכון
  `/consumer/js/app.js` (לא `/js/app.js` — זה החזיר 404).

**ממצאי CORS:** ה-CORS בקוד מקודד `"*"` ולא קורא ממשתנה סביבה. נרשם, לא תוקן
היום (ר' "נדחה במודע").

---

## סנכרון לקוח↔ספר

**Polling של תפריט שירותים (לקוח)** — `77835fb` (מוזג `e6f138a`):
- היה: עמוד פרופיל הספר טען את תפריט השירותים פעם אחת בלבד; סוכני הגרידה
  מעדכנים שירותים ברקע, אז עמוד פתוח התיישן.
- שונה: רענון כל 15 שניות בזמן שהמשתמש על `#/barber/<id>`, עם ניקוי טיימר נקי
  בעת עזיבה (ללא דליפת טיימר). קובץ: `frontend/consumer/js/app.js`.

**Cascade של מחיר לסלוטים פנויים בלבד** — `9e7bebc` (מוזג `30b4cc8`):
- היה: עריכת מחיר שירות לא התעדכנה בסלוטים הקיימים.
- שונה: עדכון מחיר שירות מתפשט ל-`available_slots` במצב `free` בלבד — סלוטים
  `locked`/`booked` שומרים את המחיר שהלקוח שריין/שילם. קובץ: `frontend/dashboard/js/data.js`.

**תיקון שורש ל-realtime בדאשבורד** — `ccc9287` (מוזג `cbc474b`):
- היה: `onAuthChange` אִפֵּס את ה-shop לפי שם האירוע. supabase-js משדר מחדש
  `SIGNED_IN` בסנכרון session בין טאבים → תקלה.
- שונה: איפוס ה-shop מותנה בשינוי **זהות המשתמש** (id), לא בשם האירוע. קובץ:
  `frontend/dashboard/js/app.js`.
- **תיקון אחד שפתר 3 סימפטומים:** (1) טעינה מחדש של הדאשבורד במעבר טאב,
  (2) חוסר ב-toast להזמנה חדשה, (3) חוסר בהתראת ביטול.

**מצב ויזואלי + החרגה לביטולים** — `d8865ac`:
- היה: הזמנות מבוטלות לא הוצגו/לא נספרו עקבי.
- שונה: התראה + הצגת הזמנות מבוטלות; ביטולים מוחרגים מחישוב ההכנסה. קובץ:
  `frontend/dashboard/js/dashboard.js`.

---

## פיצ'רים חדשים

**דילים של הרגע האחרון (3 שכבות)** — ענף `feat/dashboard-deals-and-settings` (מוזג `36ca0f1`):
- כתיבה (דאשבורד) — `0a3e43b`: toggle "סמן כדיל" ב-AddSlotModal + שדה `deal_price`.
  קבצים: `frontend/dashboard/js/dashboard.js`, `frontend/dashboard/js/data.js`.
- Pass-through (backend) — `4b8a503`: שדות `is_deal`/`deal_price` במודל התגובה
  `Slot`. קובץ: `backend/app/models/schemas.py` (ללא מיגרציה — העמודות קיימות).
- תצוגה (לקוח) — `106dc0a`: כרטיס סלוט + confirm-sheet מציגים מחיר דיל + מחיר
  מקורי מחוק + תג "🔥 מבצע". קובץ: `frontend/consumer/js/app.js`.
- תמחור מודע-דיל בהזמנות/סטטיסטיקה/לוח — `3bf1e1a`: תג "🔥 דיל" בשורות
  סלוט פנוי + מחיר דיל בכרטיסי הזמנה. קובץ: `frontend/dashboard/js/dashboard.js`.
- היסטוריית לקוח מודעת-דיל — `71aec7f`: מיגרציה
  `20260630000000_deal_aware_booking_history.sql` — ה-RPC `bookings_for_user`
  מחזיר `deal_price` כשהסלוט הוא דיל (חתימה ללא שינוי).
- החרגת ביטולים בסטטיסטיקת הדיל — `51ba5f2`: ביטולים נשארים מחוץ להכנסה גם
  אחרי החלת לוגיקת `is_deal ? deal_price : price`.

**טופס הגדרות פרטי-עסק** — `36720ee`:
- שורת "פרטי העסק" ב-SettingsTab מובילה למודל עריכה (שם/כתובת/טלפון/שעות פתיחה)
  הקורא ל-`updateShop`. קובץ: `frontend/dashboard/js/dashboard.js`.

**מקטע "הצוות שלנו" (לקוח)** — `297ed8c` (מוזג `83684b3`):
- היה: צוות המספרה (טבלת `staff`, בשימוש פנימי לשיוך סלוטים) מעולם לא הוצג ללקוח.
- שונה: `fetchStaff(shopId)` (פעילים בלבד) + `staffRowHTML` (אייקון אדם גנרי —
  לטבלת staff אין עמודת תמונה); מוצג inline מתחת לתפריט השירותים, מוסתר עד
  שנטען לפחות חבר צוות אחד. קבצים: `frontend/consumer/js/app.js`,
  `frontend/consumer/js/shopData.js`.

**Endpoint גאוקוד מאובטח + גאוקוד באונבורדינג** — `8c6b918` + `658cc73`:
- היה: האונבורדינג הסתמך על GPS דפדפן לא-אמין למיקום המספרה.
- שונה: `GET /geocode` מאובטח (Bearer של ה-JWT של הספר) שממיר כתובת חופשית
  לקואורדינטות; האונבורדינג ממיר את כתובת העסק במקום GPS. קבצים:
  `backend/app/routers/geocode.py`, `backend/app/dependencies.py`, `backend/app/main.py`,
  `backend/app/models/schemas.py`; `frontend/dashboard/js/data.js`,
  `frontend/dashboard/js/onboarding.js`.

---

## איכות דאטה

**זיהום ב-Discovery — חקירה ותיקון** — `76639a6` (מוזג `8371a65`):
- ממצא: ~915 "מספרות" שהתגלו נכתבו ע"י ריצת discovery **מוקדמת ללא המסווג**
  (`8dccdc1`, 0 קריאות OpenAI — כתבה כל תוצאת `places_nearby` ללא סינון). מיגרציה
  `20260626300000` נתנה ברירת-מחדל גורפת `place_type='barber_shop'` לכל ה-NULL,
  אז לא-מספרות (השכרת רכב, מרפאות, שמלות כלה) קיבלו תווית `barber_shop`.
  **~89% מ-915 לא היו מספרות.**
- תיקון: סוכן `ReclassifyAgent` חדש מריץ את **המסווג הקיים המאומת**
  (`_is_mens_barbershop`) מחדש על השורות הישנות, מוריד לא-מספרות ל-`place_type='non_barber'`
  (נשמרות ל-audit, מוחרגות מכל שאילתה צרכן/סוכן). תוצאה: **99 מספרות אמיתיות מאושרות**.
- סינון `place_type IN ('barber_shop','hair_care')` נוסף לבחירת היעדים של
  סוכני enrichment + scraping (תואם את ה-RPC `barbershops_within_radius`).
- קבצים: `backend/app/agents/reclassify_agent.py`, `backend/scripts/run_reclassify.py`,
  `backend/app/agents/enrichment_agent.py`, `backend/app/agents/scraping_agent.py`;
  מיגרציה `20260630010000_add_google_types.sql` (עמודת `google_types` כסמן עיבוד).
- תיקון בדיקות: `43e08d8` — עדכון ה-mocks של `fetch_targets` לשרשרת `.in_` החדשה
  (קבצים: `backend/tests/test_enrichment_agent.py`, `backend/tests/test_scraping_agent.py`).

**הרחבת allowlist לאמון-מחיר** — `69f387c` (מוזג `b6d676e`):
- היה: `is_pricing_source` אִפֵּס מחיר/משך לכל פלטפורמה מחוץ ל-`{tor4you, glamera}`,
  אז מספרות אמיתיות על calmark/eztor/cut-shave (מסווגות `custom`) איבדו מחירים.
- שונה: כל פלטפורמה אומתה בנפרד מול עמוד חי לפני הוספה — calmark/eztor/cut-shave
  ✅ (מחירים מובנים), **katzuz נדחתה** (עמוד שיווקי, ₪0). נוספו markers ב-`detect.py`
  ו-`_PRICING_PLATFORMS` ב-`extraction.py`.
- מיגרציה `20260630020000_upsert_service_fill_price.sql`: ה-RPC `upsert_service`
  היה insert-only (`on conflict do nothing`) — ריצת enrichment חוזרת לא יכלה
  למלא מחיר חסר. שונה ל-`coalesce(existing, excluded)` (gap-fill בלבד; לא דורס
  מחיר שהוזן ידנית ע"י בעל העסק).
- קבצים: `backend/app/agents/booking_adapters/detect.py`, `backend/app/agents/extraction.py`.

**ריצות enrichment:** מילוי שירותים+צוות עבור מספרות אמיתיות; אחרי תיקון ה-RPC
+ ה-allowlist, מחירים אמיתיים אוכלסו (Dudu: 0→17 שירותים עם מחיר; calmark/eztor/
cut-shave פעילים; katzuz נשאר null כצפוי).

**ריצת scraping + מגבלה מבנית מתועדת:**
- תוצאה: 5 סלוטים מ-34 מספרות שעובדו (רוב החזירו "0 slots").
- שורש: גרידת טקסט שטוחה לא מגיעה ל-grid סלוטים שמאחורי אינטראקציה — calmark/
  eztor/smartor מציגות תפריט בטעינה (לכן enrichment קיבל מחירים) אך מסתירות
  זמינות מאחורי בחירת שירות→ספר→תאריך. הגדלת `_RENDER_WAIT_MS` לא תעזור.

**קיצור-דרך API ל-calmark (התגלה, לא נבנה)** — `7d31179` (ענף `docs/calmark-api-note`):
- calmark.io חושפת API נקי של ASP.NET page-methods: `POST /Pages/Page.aspx/<Method>`,
  JSON פשוט, ללא auth/CSRF עם כותרות דפדפן רגילות. מתועדות `GetPageData`
  ו-`GetBusinessReviewsFiltered`; `businessId` לכל מספרה דרך `GetPageData`.
- חסר: שם שיטת הזמינות/סלוטים — סשן עתידי. קובץ: `backend/app/agents/scraping_agent.py`
  (TODO).

**ניקיון:**
- מחיקת shops של fixtures לבדיקות E2E (`Test Cuts E2E`, `Jerusalem Test Cuts`) +
  44 סלוטים + 4 הזמנות נלוות (סדר FK בטוח).
- מחיקת שירותי-זבל: שורת "השכרת רכב" של Eldan; 140 שירותים שנכתבו לשורות
  `non_barber` בריצת reprice שגויה (שכוונה ליעדים הלא-נכונים בגלל סינון place_type
  שלא מוזג בזמן ל-develop).
- היגיינת ענפים: TODO לפער ה-booking_url נרשם — `dd95921` (ענף `chore/log-booking-url-gap`).
- היגיינת ענפים: תויג `archive/Develope` (שימור היסטוריה לפני מחיקה); נמחקו הענפים
  הישנים `Develope` ו-`develop-phase-4` (שניהם אומתו כמוחלפים לחלוטין ע"י `main`
  לפני ההסרה).

---

## נדחה במודע — לא היום

- **`ENVIRONMENT=production`** לא הוגדר בפרודקשן → ה-admin router (dev-only) נשאר
  mounted. **מכוון** — נחוץ להדגמת הרשמת ספרים. `/health` מציג `"environment":"development"`.
- **CORS** קורא מהקוד `"*"` קשיח במקום ממשתנה סביבה.
- **Playwright + `AGENTS_AUTOSTART` ב-Railway** לגרידה חיה רציפה.
- **9 מספרות עם booking_url של עמוד-בית שיווקי** במקום deep-link אמיתי (Davidi Levi,
  Barberia, Aviel, ברבר 7, Oded, homie's, KID-CUT, מספרת יצחק; katzuz מוכח שיווקי).
  TODO נרשם ב-`backend/app/agents/discovery_agent.py` (`dd95921`).
- **פלטפורמת megator** — חילוץ מחיר מתחת לרף האיכות (404 על שורה אחת, מחיר בודד
  ללא zוג משך). לא נוספה ל-allowlist.
- **אדפטר סלוטים ל-calmark** — קיצור ה-API נמצא, אך שם שיטת הזמינות לא נלכד עדיין.
