// Owner data layer — all calls run as the authenticated barber under owner RLS.
import { supabase } from "./supabaseClient.js";

async function uid() {
  const { data } = await supabase.auth.getUser();
  return data.user?.id;
}

// Unwrap a Supabase response, logging + rethrowing on error so failures are
// visible in the console (and surfaced by the dashboard's loaders) instead of
// hanging silently.
function unwrap(label, res) {
  if (res.error) {
    console.error(`[data] ${label} failed:`, res.error.message || res.error, res.error);
    throw new Error(`${label}: ${res.error.message || res.error}`);
  }
  return res.data;
}

// The barbershop owned by the current barber (null during onboarding).
export async function getMyShop() {
  const me = await uid();
  if (!me) return null;
  const data = unwrap(
    "getMyShop",
    await supabase.from("barbershops").select("*").eq("owner_id", me).limit(1)
  );
  return data?.[0] || null;
}

// Create the barber's shop (PostGIS location as EWKT; owner_id must = auth.uid()).
export async function createShop({ name, address, phone, lat, lng, opening_hours, photo_url }) {
  const me = await uid();
  const row = {
    name,
    address: address || null,
    phone: phone || null,
    photo_url: photo_url || null,
    place_type: "barber_shop",
    is_active_partner: true,
    owner_id: me,
    opening_hours: opening_hours || null,
    location: lat != null && lng != null ? `SRID=4326;POINT(${lng} ${lat})` : null,
  };
  const { data, error } = await supabase.from("barbershops").insert(row).select("*").single();
  if (error) throw error;
  return data;
}

export async function updateShop(shopId, patch) {
  const { data, error } = await supabase
    .from("barbershops")
    .update(patch)
    .eq("id", shopId)
    .select("*")
    .single();
  if (error) throw error;
  return data;
}

// Appointments = consumer bookings for this owner's shop (RLS already scopes to
// the owner). Joined with the slot for service/time/price.
export async function listAppointments() {
  const data = unwrap(
    "listAppointments",
    await supabase
      .from("bookings")
      .select(
        "id,customer_name,customer_phone,status,created_at," +
          "slot:available_slots(id,service_name,slot_time,price,staff_id,barbershop_id,status)"
      )
      .order("created_at", { ascending: false })
  );
  return (data || []).filter((b) => b.slot); // drop any orphaned rows
}

// ── Slots ────────────────────────────────────────────────────────────────────
export async function listSlots(shopId) {
  return (
    unwrap(
      "listSlots",
      await supabase
        .from("available_slots")
        .select("id,service_name,slot_time,price,status,staff_id")
        .eq("barbershop_id", shopId)
        .order("slot_time", { ascending: true })
    ) || []
  );
}
export async function createSlot(shopId, { service_name, price, slot_time, staff_id }) {
  const { data, error } = await supabase
    .from("available_slots")
    .insert({ barbershop_id: shopId, service_name, price, slot_time, staff_id: staff_id || null })
    .select("id")
    .single();
  if (error) throw error;
  return data;
}
export async function deleteSlot(id) {
  const { error } = await supabase.from("available_slots").delete().eq("id", id);
  if (error) throw error;
}

// ── Services ─────────────────────────────────────────────────────────────────
export async function listServices(shopId) {
  return (
    unwrap(
      "listServices",
      await supabase
        .from("services")
        .select("id,name,category,price,duration_mins,staff_id,is_active")
        .eq("shop_id", shopId)
        .order("price", { ascending: true })
    ) || []
  );
}
export async function createService(shopId, s) {
  const { data, error } = await supabase
    .from("services")
    .insert({ shop_id: shopId, ...s })
    .select("*")
    .single();
  if (error) throw error;
  return data;
}
export async function updateService(id, patch) {
  const { error } = await supabase.from("services").update(patch).eq("id", id);
  if (error) throw error;
}
export async function deleteService(id) {
  const { error } = await supabase.from("services").delete().eq("id", id);
  if (error) throw error;
}

// ── Staff ────────────────────────────────────────────────────────────────────
export async function listStaff(shopId) {
  return (
    unwrap(
      "listStaff",
      await supabase
        .from("staff")
        .select("id,name,is_active")
        .eq("shop_id", shopId)
        .order("name", { ascending: true })
    ) || []
  );
}
export async function createStaff(shopId, name) {
  const { data, error } = await supabase
    .from("staff")
    .insert({ shop_id: shopId, name, is_active: true })
    .select("*")
    .single();
  if (error) throw error;
  return data;
}
export async function updateStaff(id, patch) {
  const { error } = await supabase.from("staff").update(patch).eq("id", id);
  if (error) throw error;
}
export async function deleteStaff(id) {
  const { error } = await supabase.from("staff").delete().eq("id", id);
  if (error) throw error;
}

// Realtime: re-run `cb` on any booking/slot change for this shop.
export function subscribeShop(shopId, cb) {
  const ch = supabase
    .channel(`owner:${shopId}`)
    .on("postgres_changes", { event: "*", schema: "public", table: "available_slots", filter: `barbershop_id=eq.${shopId}` }, cb)
    .on("postgres_changes", { event: "*", schema: "public", table: "bookings" }, cb)
    .subscribe();
  return () => supabase.removeChannel(ch);
}
