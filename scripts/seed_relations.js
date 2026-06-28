// Backfill relational data (staff → services → available_slots) for the mock
// barbershops created by seed_barbershops.js (google_place_id like 'seed:%').
//
// Run:
//   cd scripts && node seed_relations.js
//
// Credentials auto-load from the repo-root .env (SERVICE ROLE key — bypasses RLS).
//
// FK chain & order matter:
//   barbershops → staff (shop_id)
//   barbershops → services (shop_id; staff_id null = shop-wide menu)
//   barbershops → available_slots (barbershop_id, staff_id) — service is DENORMALIZED:
//     a slot copies service_name + price from one of the shop's services.
//
// Idempotency: service_role holds INSERT but not DELETE, so we can't pre-clean.
// Instead we SKIP any seed shop that already has staff — re-runs won't duplicate.

const fs = require("fs");
const path = require("path");
const { createClient } = require("@supabase/supabase-js");

// ── repo-root .env (.env wins over a stale shell value) ──────────────────────
(function loadRootEnv() {
  const envPath = path.resolve(__dirname, "..", ".env");
  if (!fs.existsSync(envPath)) return;
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
})();

const SUPABASE_URL = process.env.SUPABASE_URL || "https://ekugfzrmitvoiamevtfa.supabase.co";
const SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!SERVICE_ROLE_KEY) {
  console.error("✗ Missing SUPABASE_SERVICE_ROLE_KEY (checked process.env and ../.env).");
  process.exit(1);
}
const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY, { auth: { persistSession: false } });

// ── tunables ─────────────────────────────────────────────────────────────────
const HORIZON_DAYS = 7; // slots generated for the next N days (today..+6)
const SLOTS_PER_DAY = 4; // approx free slots per barber per day
const SLOT_CHUNK = 500; // rows per available_slots insert

// ── mock pools ───────────────────────────────────────────────────────────────
const BARBER_NAMES = [
  "אבי", "משה", "דני", "יוסי", "רון", "איתי", "עידן", "שגיא", "ניר", "נועם",
  "אלי", "קובי", "טל", "עומר", "ליאור", "דור", "אסף", "מאור", "יהונתן", "רועי",
];
// Service menu: realistic Hebrew names, price (₪, int), duration (mins), category.
const MENU = [
  { name: "תספורת גבר",        category: "תספורת", min: 60,  max: 90,  dur: 30 },
  { name: "פייד",              category: "תספורת", min: 70,  max: 100, dur: 40 },
  { name: "עיצוב זקן",         category: "זקן",    min: 30,  max: 50,  dur: 20 },
  { name: "תספורת + זקן",      category: "חבילה",  min: 90,  max: 130, dur: 50 },
  { name: "תספורת ילדים",      category: "תספורת", min: 40,  max: 60,  dur: 25 },
  { name: "גילוח מגבת חמה",    category: "זקן",    min: 50,  max: 70,  dur: 30 },
];
// Business-hours start times (local), on the hour and half-hour.
const SLOT_HOURS = ["10:00", "11:00", "12:00", "13:30", "15:00", "16:00", "17:00", "18:00", "18:30"];

const rand = (min, max) => min + Math.random() * (max - min);
const randInt = (min, max) => Math.floor(rand(min, max + 1));
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
// Distinct random sample of `k` items.
function sample(arr, k) {
  const copy = [...arr];
  const out = [];
  while (out.length < k && copy.length) out.push(copy.splice(Math.floor(Math.random() * copy.length), 1)[0]);
  return out;
}

// Build a future Date for `dayOffset` days from now at "HH:MM".
function slotDate(dayOffset, hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  const d = new Date();
  d.setDate(d.getDate() + dayOffset);
  d.setHours(h, m, 0, 0);
  return d;
}

function buildServices(shopId) {
  return sample(MENU, randInt(4, 6)).map((s) => ({
    shop_id: shopId,
    name: s.name,
    category: s.category,
    duration_mins: s.dur,
    price: randInt(s.min, s.max),
    staff_id: null, // shop-wide menu
  }));
}

// Slots for a WHOLE shop. Unique constraint is (barbershop_id, slot_time,
// service_name) — so within a shop, barbers sharing a timeslot must each get a
// DISTINCT service. For every future business-hour datetime we pick a random
// subset of barbers and hand each a distinct service (name + price copied).
// Each barber appears at ~INCLUDE_P of datetimes → their own ~4/day schedule.
const INCLUDE_P = SLOTS_PER_DAY / SLOT_HOURS.length; // P a barber takes a given hour
function buildSlotsForShop(shopId, staff, services) {
  const rows = [];
  const now = new Date();
  for (let day = 0; day < HORIZON_DAYS; day++) {
    for (const hh of SLOT_HOURS) {
      const when = slotDate(day, hh);
      if (when <= now) continue; // future only (drops past hours today)
      // Barbers wanting this datetime (fair order), capped to #services so each
      // can receive a distinct service and the (time, service) pair stays unique.
      let wanting = sample(staff, staff.length).filter(() => Math.random() < INCLUDE_P);
      if (!wanting.length) continue;
      const svcs = sample(services, services.length);
      const k = Math.min(wanting.length, svcs.length);
      for (let i = 0; i < k; i++) {
        rows.push({
          barbershop_id: shopId,
          staff_id: wanting[i].id,
          service_name: svcs[i].name,
          price: svcs[i].price,
          slot_time: when.toISOString(),
          // status omitted -> defaults to 'free'
        });
      }
    }
  }
  return rows;
}

async function insertSlotsChunked(rows) {
  let inserted = 0;
  for (let i = 0; i < rows.length; i += SLOT_CHUNK) {
    const chunk = rows.slice(i, i + SLOT_CHUNK);
    const { error } = await supabase.from("available_slots").insert(chunk);
    if (error) throw new Error(`available_slots insert: ${error.message}`);
    inserted += chunk.length;
  }
  return inserted;
}

async function main() {
  const { data: shops, error: shopErr } = await supabase
    .from("barbershops")
    .select("id, name")
    .like("google_place_id", "seed:%");
  if (shopErr) {
    console.error("✗ Failed loading seed shops:", shopErr.message);
    process.exit(1);
  }
  console.log(`Found ${shops.length} seeded shops.`);

  const totals = { shops: 0, skipped: 0, staff: 0, services: 0, slots: 0 };

  for (const shop of shops) {
    // Idempotency: skip shops that already have staff.
    const { count: staffCount, error: cErr } = await supabase
      .from("staff")
      .select("id", { count: "exact", head: true })
      .eq("shop_id", shop.id);
    if (cErr) throw new Error(`staff count: ${cErr.message}`);
    if (staffCount > 0) {
      totals.skipped++;
      continue;
    }

    // 1) Staff (2–4 barbers).
    const teamNames = sample(BARBER_NAMES, randInt(2, 4));
    const { data: staff, error: sErr } = await supabase
      .from("staff")
      .insert(teamNames.map((name) => ({ shop_id: shop.id, name, is_active: true })))
      .select("id, name");
    if (sErr) throw new Error(`staff insert (${shop.name}): ${sErr.message}`);

    // 2) Services (shop-wide menu).
    const { data: services, error: svErr } = await supabase
      .from("services")
      .insert(buildServices(shop.id))
      .select("id, name, price");
    if (svErr) throw new Error(`services insert (${shop.name}): ${svErr.message}`);

    // 3) Slots — every barber gets their own schedule (distinct service per
    //    shared timeslot to satisfy the (shop, time, service) unique key).
    const slotRows = buildSlotsForShop(shop.id, staff, services);
    const slotsInserted = await insertSlotsChunked(slotRows);

    totals.shops++;
    totals.staff += staff.length;
    totals.services += services.length;
    totals.slots += slotsInserted;
  }

  console.log("\n✓ Done.");
  console.log(`   Shops populated : ${totals.shops}  (skipped ${totals.skipped} already-populated)`);
  console.log(`   Staff inserted  : ${totals.staff}`);
  console.log(`   Services        : ${totals.services}`);
  console.log(`   Free slots      : ${totals.slots}`);
  console.log("\nCleanup later (cascade by seed shop):");
  console.log("  delete from available_slots where barbershop_id in (select id from barbershops where google_place_id like 'seed:%');");
  console.log("  delete from services       where shop_id       in (select id from barbershops where google_place_id like 'seed:%');");
  console.log("  delete from staff          where shop_id       in (select id from barbershops where google_place_id like 'seed:%');");
}

main().catch((e) => {
  console.error("✗ Error:", e.message || e);
  process.exit(1);
});
