// Direct Supabase reads for the barbershop profile (Phase 1).
//
// These tables have anon-read RLS enabled, so the consumer app reads them
// straight from Supabase — no backend round-trip. Slots/bookings still go
// through the FastAPI backend (api.js); only the static profile data
// (services menu, scraped Google reviews) is fetched here.
//
// Every field except the primary key may be null — the render layer must
// degrade gracefully. Callers should treat a thrown error as "section
// unavailable" and fall back to an empty list.
import { supabase } from "./supabaseClient.js";

// Services menu for a shop. Note the column is `shop_id` (NOT barbershop_id),
// and the "barber" is a FK to staff — embedded as `staff.name`.
export async function fetchServices(shopId) {
  const { data, error } = await supabase
    .from("services")
    // Embedded staff is inner-joined on is_active so a service whose (only)
    // barber was deactivated still shows, but an inactive barber's name is hidden.
    .select("id, name, price, duration_mins, category, staff:staff_id ( name, is_active )")
    .eq("shop_id", shopId)
    .eq("is_active", true) // hide deactivated services from customers
    .order("category", { ascending: true, nullsFirst: false })
    .order("price", { ascending: true, nullsFirst: false });
  if (error) throw error;
  return (data || []).map((s) => ({
    id: s.id,
    name: s.name,
    price: s.price, // may be null → "מחיר לפי בקשה"
    duration_mins: s.duration_mins, // may be null → hide chip
    category: s.category, // may be null
    // hide the barber name when that staff member is deactivated
    barber: s.staff?.is_active ? s.staff.name : null,
  }));
}

// Scraped external (Google) reviews. Column here is `barbershop_id`.
export async function fetchExternalReviews(shopId) {
  const { data, error } = await supabase
    .from("external_reviews")
    .select("id, author, rating, text, source, reviewed_at")
    .eq("barbershop_id", shopId)
    .order("reviewed_at", { ascending: false, nullsFirst: false })
    .limit(50);
  if (error) throw error;
  return data || [];
}
