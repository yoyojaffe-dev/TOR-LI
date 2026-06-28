// Seed a demo barber account (Supabase Auth) and make it the owner of a seeded
// shop so the dashboard shows real appointments immediately.
//
//   cd scripts && node seed_barber.js
//
// Uses the service-role key (Auth Admin API) to create a PRE-CONFIRMED user —
// global email confirmation stays on; we just don't require an inbox for the demo.

const fs = require("fs");
const path = require("path");
const { createClient } = require("@supabase/supabase-js");

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
  console.error("✗ Missing SUPABASE_SERVICE_ROLE_KEY.");
  process.exit(1);
}
const admin = createClient(SUPABASE_URL, SERVICE_ROLE_KEY, { auth: { persistSession: false } });

const EMAIL = "barber@torli.dev";
const PASSWORD = "torli1234";
const SHOP_ID = "31a04333-d8af-4303-8c0e-3c3cb73930c2"; // מספרת גלי (has a real phase-5 booking)

async function findUserByEmail(email) {
  // paginate listUsers until found (small dataset)
  for (let page = 1; page <= 20; page++) {
    const { data, error } = await admin.auth.admin.listUsers({ page, perPage: 200 });
    if (error) throw error;
    const u = data.users.find((x) => x.email === email);
    if (u) return u;
    if (data.users.length < 200) break;
  }
  return null;
}

async function main() {
  // 1) Create (or reuse) a pre-confirmed auth user.
  let userId;
  const created = await admin.auth.admin.createUser({
    email: EMAIL,
    password: PASSWORD,
    email_confirm: true,
    user_metadata: { full_name: "ספר הדגמה" },
  });
  if (created.error) {
    if (/already.*registered|exists/i.test(created.error.message)) {
      const existing = await findUserByEmail(EMAIL);
      if (!existing) throw new Error("user exists but not found via listUsers");
      userId = existing.id;
      console.log("• Auth user already existed — reusing.");
    } else {
      throw created.error;
    }
  } else {
    userId = created.data.user.id;
    console.log("• Created auth user.");
  }

  // 2) Upsert the public.users profile row (role=owner).
  const { error: uErr } = await admin
    .from("users")
    .upsert({ id: userId, role: "owner", full_name: "ספר הדגמה", phone: "0540000000" });
  if (uErr) throw uErr;

  // 3) Make this barber the owner of the demo shop.
  const { error: oErr } = await admin
    .from("barbershops")
    .update({ owner_id: userId })
    .eq("id", SHOP_ID);
  if (oErr) throw oErr;

  console.log("\n✓ Demo barber ready.");
  console.log(`   email:    ${EMAIL}`);
  console.log(`   password: ${PASSWORD}`);
  console.log(`   owns shop: ${SHOP_ID} (מספרת גלי)`);
}

main().catch((e) => {
  console.error("✗ Error:", e.message || e);
  process.exit(1);
});
