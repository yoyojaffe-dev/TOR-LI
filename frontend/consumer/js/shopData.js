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
    .select("id, name, price, duration_mins, category, staff:staff_id ( name )")
    .eq("shop_id", shopId)
    .order("category", { ascending: true, nullsFirst: false })
    .order("price", { ascending: true, nullsFirst: false });
  if (error) throw error;
  return (data || []).map((s) => ({
    id: s.id,
    name: s.name,
    price: s.price, // may be null → "מחיר לפי בקשה"
    duration_mins: s.duration_mins, // may be null → hide chip
    category: s.category, // may be null
    barber: s.staff?.name ?? null, // may be null → hide
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
