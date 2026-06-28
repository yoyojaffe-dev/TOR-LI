// Seed the `barbershops` table with high-quality mock data spread across Israel
// (Kiryat Shmona → Eilat) to exercise the map viewport-driven fetching.
//
// Run:
//   cd scripts && npm install && node seed_barbershops.js
//
// Credentials: auto-loaded from the repo-root .env (SUPABASE_URL +
// SUPABASE_SERVICE_ROLE_KEY), or override via real environment variables.
// The SERVICE ROLE key bypasses RLS — required to insert. Never ship it client-side.
//
// Idempotent: every seeded row is tagged google_place_id = "seed:<city>:<n>";
// the script removes prior seed rows before inserting, so re-runs stay clean.

const fs = require("fs");
const path = require("path");
const { createClient } = require("@supabase/supabase-js");

// ── Load repo-root .env (no dotenv dependency) ───────────────────────────────
function loadRootEnv() {
  const envPath = path.resolve(__dirname, "..", ".env");
  if (!fs.existsSync(envPath)) return;
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!m) continue;
    const key = m[1];
    let val = m[2].replace(/^["']|["']$/g, ""); // strip surrounding quotes
    // .env is the source of truth for this seed script — let it override any
    // stale value already exported in the shell (e.g. an anon key), which would
    // otherwise cause "permission denied" on insert/delete.
    process.env[key] = val;
  }
}
loadRootEnv();

const SUPABASE_URL = process.env.SUPABASE_URL || "https://ekugfzrmitvoiamevtfa.supabase.co";
const SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SERVICE_ROLE_KEY) {
  console.error(
    "✗ Missing SUPABASE_SERVICE_ROLE_KEY (checked process.env and ../.env).\n" +
      "  Set it and re-run:  SUPABASE_SERVICE_ROLE_KEY=... node seed_barbershops.js"
  );
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

// ── City distribution (north → south, weighted by size) ──────────────────────
const CITIES = [
  { key: "kiryat-shmona", he: "קריית שמונה", lat: 33.2074, lng: 35.5701, n: 3 },
  { key: "nahariya",      he: "נהריה",        lat: 33.0058, lng: 35.0944, n: 3 },
  { key: "tiberias",      he: "טבריה",        lat: 32.7959, lng: 35.5300, n: 3 },
  { key: "haifa",         he: "חיפה",         lat: 32.7940, lng: 34.9896, n: 6 },
  { key: "nazareth",      he: "נצרת",         lat: 32.7009, lng: 35.3035, n: 3 },
  { key: "netanya",       he: "נתניה",        lat: 32.3215, lng: 34.8532, n: 4 },
  { key: "tel-aviv",      he: "תל אביב",      lat: 32.0853, lng: 34.7818, n: 8 },
  { key: "ramat-gan",     he: "רמת גן",       lat: 32.0823, lng: 34.8141, n: 3 },
  { key: "rishon",        he: "ראשון לציון",  lat: 31.9730, lng: 34.7925, n: 4 },
  { key: "ashdod",        he: "אשדוד",        lat: 31.8040, lng: 34.6553, n: 4 },
  { key: "jerusalem",     he: "ירושלים",      lat: 31.7683, lng: 35.2137, n: 8 },
  { key: "beersheba",     he: "באר שבע",      lat: 31.2530, lng: 34.7915, n: 5 },
  { key: "eilat",         he: "אילת",         lat: 29.5581, lng: 34.9482, n: 3 },
];

const NAME_PREFIX = ["מספרת", "ברבר", "סטודיו", "הסלון של", "תספורות", "בית עיצוב"];
const NAME_CORE = [
  "אבי", "משה", "דני", "יוסי", "רון", "איתי", "עידן", "שגיא", "ניר", "גלי",
  "שיר", "נועם", "אלי", "קובי", "טל", "עומר", "ליאור", "דור", "אסף", "מאור",
];
const STREETS = [
  "הרצל", "ויצמן", "בן גוריון", "דיזנגוף", "ז׳בוטינסקי", "אלנבי",
  "רוטשילד", "סוקולוב", "ביאליק", "הנשיא", "העצמאות", "כצנלסון",
];
// Stable Unsplash barbershop photos; ~20% of shops get null to test the
// gradient placeholder fallback in the UI.
const PHOTOS = [
  "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=800&q=80",
  "https://images.unsplash.com/photo-1521590832167-7bcbfaa6381f?w=800&q=80",
  "https://images.unsplash.com/photo-1599351431202-1e0f0137899a?w=800&q=80",
  "https://images.unsplash.com/photo-1585747860715-2ba37e788b70?w=800&q=80",
  "https://images.unsplash.com/photo-1622286342621-4bd786c2447c?w=800&q=80",
];

const rand = (min, max) => min + Math.random() * (max - min);
const randInt = (min, max) => Math.floor(rand(min, max + 1));
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const round = (x, dp = 6) => Number(x.toFixed(dp));

function buildRow(city, i, usedNames) {
  // Cluster inside the city (~±2 km) so pins look natural, not stacked.
  const lat = round(city.lat + rand(-0.018, 0.018));
  const lng = round(city.lng + rand(-0.022, 0.022));

  // Unique-ish display name.
  let name;
  do {
    name = `${pick(NAME_PREFIX)} ${pick(NAME_CORE)}`;
  } while (usedNames.has(name) && usedNames.size < NAME_PREFIX.length * NAME_CORE.length);
  usedNames.add(name);

  const hasPhoto = Math.random() > 0.2;
  const photo = hasPhoto ? pick(PHOTOS) : null;

  return {
    name,
    address: `${pick(STREETS)} ${randInt(1, 120)}, ${city.he}`,
    phone: `+9725${randInt(10000000, 99999999)}`,
    booking_url: null,
    google_place_id: `seed:${city.key}:${i + 1}`,
    // PostGIS geography expects EWKT in LON LAT order.
    location: `SRID=4326;POINT(${lng} ${lat})`,
    opening_hours: null,
    is_active_partner: Math.random() > 0.5,
    photo_url: photo,
    photo_urls: hasPhoto ? [photo] : [],
    rating: round(rand(3.7, 5.0), 1),
    rating_count: randInt(5, 450),
    // MUST be one of these — the map RPC (barbershops_within_radius) filters on
    // place_type in ('barber_shop','hair_care'); anything else is invisible.
    place_type: Math.random() > 0.15 ? "barber_shop" : "hair_care",
    booking_platform: null,
  };
}

function buildAll() {
  const usedNames = new Set();
  const rows = [];
  for (const city of CITIES) {
    for (let i = 0; i < city.n; i++) rows.push(buildRow(city, i, usedNames));
  }
  return rows;
}

async function main() {
  const rows = buildAll();
  console.log(`Generated ${rows.length} mock barbershops across ${CITIES.length} cities.`);

  // Idempotency: try to clear prior seed rows so re-runs don't accumulate.
  // Best-effort — the service_role may only hold INSERT (not DELETE) on this
  // table; if so, warn and continue rather than aborting the whole seed.
  const { error: delErr, count: delCount } = await supabase
    .from("barbershops")
    .delete({ count: "exact" })
    .like("google_place_id", "seed:%");
  if (delErr) {
    console.warn(`⚠ Could not clear previous seed rows (${delErr.message}).`);
    console.warn(
      "  Continuing with insert. Re-runs may duplicate — clean up with:\n" +
        "  delete from barbershops where google_place_id like 'seed:%';"
    );
  } else {
    console.log(`Removed ${delCount ?? 0} previous seed row(s).`);
  }

  const { data, error } = await supabase
    .from("barbershops")
    .insert(rows)
    .select("id, name, place_type");
  if (error) {
    console.error("✗ Insert failed:", error.message);
    process.exit(1);
  }

  console.log(`✓ Inserted ${data.length} barbershops.`);
  for (const c of CITIES) console.log(`   ${c.he.padEnd(14)} ${c.n}`);
  console.log("\nMap check: switch to map view, pan to any city, tap “חפש באזור זה”.");
  console.log("Cleanup later:  delete from barbershops where google_place_id like 'seed:%';");
}

main().catch((e) => {
  console.error("✗ Unexpected error:", e);
  process.exit(1);
});
