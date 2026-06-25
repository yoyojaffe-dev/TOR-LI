// Supabase Realtime: push available_slots changes straight into the app.
import { supabase } from "./supabaseClient.js";

// Subscribe to slot changes. Optionally scope to one barbershop.
// onChange receives { eventType, new, old }.
export function subscribeToSlots({ barbershopId = null, onChange }) {
  const filter = barbershopId ? `barbershop_id=eq.${barbershopId}` : undefined;

  const channel = supabase
    .channel(barbershopId ? `slots:${barbershopId}` : "slots:all")
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "available_slots", filter },
      (payload) =>
        onChange({ eventType: payload.eventType, new: payload.new, old: payload.old })
    )
    .subscribe();

  // Return an unsubscribe handle.
  return () => supabase.removeChannel(channel);
}
