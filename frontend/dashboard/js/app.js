// Management dashboard — React logic, buildless (React + htm from CDN ESM).
// Lets a barber view their live slots (subscribed via Supabase Realtime).
import { createElement } from "https://esm.sh/react@18";
import { createRoot } from "https://esm.sh/react-dom@18/client";
import { useEffect, useState } from "https://esm.sh/react@18";
import htm from "https://esm.sh/htm@3";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { api } from "./api.js";
import { config } from "./config.js";

const html = htm.bind(createElement);
const supabase = createClient(config.SUPABASE_URL, config.SUPABASE_ANON_KEY);

function SlotRow({ slot }) {
  return html`<tr>
    <td>${new Date(slot.slot_time).toLocaleString()}</td>
    <td>${slot.service_name}</td>
    <td>${slot.price ?? "—"}</td>
    <td>${slot.status}</td>
  </tr>`;
}

function Dashboard() {
  // Barbershop id comes from the URL (?shop=<uuid>) — wired to real auth later.
  const shopId = new URLSearchParams(location.search).get("shop");
  const [slots, setSlots] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!shopId) {
      setError("Add ?shop=<barbershop_id> to the URL");
      return;
    }
    api.listSlots(shopId).then(setSlots).catch((e) => setError(e.message));

    const channel = supabase
      .channel(`dash:${shopId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "available_slots", filter: `barbershop_id=eq.${shopId}` },
        () => api.listSlots(shopId).then(setSlots)
      )
      .subscribe();
    return () => supabase.removeChannel(channel);
  }, [shopId]);

  if (error) return html`<p class="error">${error}</p>`;
  return html`
    <div>
      <h1>Tor-li — Slots</h1>
      <table>
        <thead>
          <tr><th>Time</th><th>Service</th><th>Price</th><th>Status</th></tr>
        </thead>
        <tbody>
          ${slots.map((s) => html`<${SlotRow} key=${s.id} slot=${s} />`)}
        </tbody>
      </table>
    </div>
  `;
}

createRoot(document.getElementById("root")).render(html`<${Dashboard} />`);
