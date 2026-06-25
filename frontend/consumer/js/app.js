// Consumer app orchestrator: ties geo -> radius search -> map -> slots -> booking,
// and keeps slots live via Supabase Realtime.
//
// This wires behavior to DOM hooks (element IDs / data-attributes). Drop the
// Stitch-generated markup into index.html and keep these hook ids/attributes so
// the design lights up without re-styling.
import { api, ApiError } from "./api.js";
import { store } from "./state.js";
import { getCurrentPosition } from "./geo.js";
import { renderMap, renderBarbershopMarkers } from "./map.js";
import { subscribeToSlots } from "./realtime.js";
import { startBooking, confirmBooking, cancelBooking } from "./booking.js";

// --- DOM hooks (must exist in the Stitch markup) ---
const els = {
  map: () => document.getElementById("map"),
  shopList: () => document.getElementById("barbershop-list"),
  slotList: () => document.getElementById("slot-list"),
  lockTimer: () => document.getElementById("lock-timer"),
  bookingForm: () => document.getElementById("booking-form"),
};

let unsubscribeSlots = null;

// Tel Aviv centre — used when the user denies geolocation or it times out.
const DEFAULT_POSITION = { lat: 32.0853, lng: 34.7818 };

async function init() {
  let position;
  try {
    position = await getCurrentPosition();
  } catch {
    // Geo denied / unavailable → fall back to default so the app still loads.
    position = DEFAULT_POSITION;
    const banner = document.getElementById("geo-banner");
    if (banner) banner.hidden = false;
  }

  store.set({ position });

  try {
    const mapEl = els.map();
    if (mapEl) {
      const map = await renderMap(mapEl, position);
      store.set({ map });
    }
    await loadNearby();
  } catch (err) {
    console.error("Init failed after geo:", err);
  }
}

async function loadNearby() {
  const { position } = store.get();
  const barbershops = await api.nearbyBarbershops(position.lat, position.lng);
  store.set({ barbershops });
  renderBarbershops(barbershops);
  if (store.get().map) {
    renderBarbershopMarkers(store.get().map, barbershops, selectBarbershop);
  }
}

async function selectBarbershop(shop) {
  store.set({ selectedBarbershop: shop });
  const slots = await api.listSlots(shop.id);
  store.set({ slots });
  renderSlots(slots);

  // Live updates for this shop's slots.
  if (unsubscribeSlots) unsubscribeSlots();
  unsubscribeSlots = subscribeToSlots({
    barbershopId: shop.id,
    onChange: () => api.listSlots(shop.id).then(renderSlots),
  });
}

async function bookSlot(slotId) {
  try {
    await startBooking(slotId, {
      onTick: (remaining) => {
        const t = els.lockTimer();
        if (t) t.textContent = `${remaining}s`;
      },
      onExpire: () => alert("Lock expired — please pick a slot again."),
    });
    // Reveal the booking form (name + phone -> confirmBooking on submit).
    const form = els.bookingForm();
    if (form) form.hidden = false;
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      alert("Sorry, that slot was just taken.");
    } else {
      console.error(err);
    }
  }
}

// --- Rendering: populate the Stitch markup. Replace bodies to match real DOM. ---
function renderBarbershops(barbershops) {
  const list = els.shopList();
  if (!list) return;
  list.innerHTML = "";
  for (const b of barbershops) {
    const item = document.createElement("li");
    item.dataset.id = b.id;
    item.textContent = `${b.name} — ${Math.round(b.distance_m || 0)}m`;
    item.addEventListener("click", () => selectBarbershop(b));
    list.appendChild(item);
  }
}

function renderSlots(slots) {
  const list = els.slotList();
  if (!list) return;
  list.innerHTML = "";
  for (const s of slots) {
    const item = document.createElement("li");
    item.dataset.id = s.id;
    item.textContent = `${new Date(s.slot_time).toLocaleString()} — ${s.service_name}`;
    item.addEventListener("click", () => bookSlot(s.id));
    list.appendChild(item);
  }
}

// Booking form submit -> confirm.
document.addEventListener("submit", async (e) => {
  if (e.target.id !== "booking-form") return;
  e.preventDefault();
  const data = new FormData(e.target);
  try {
    const result = await confirmBooking(data.get("name"), data.get("phone"));
    alert(result.success ? "Booked!" : `Failed: ${result.message}`);
  } catch (err) {
    console.error(err);
  }
});

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  if (unsubscribeSlots) unsubscribeSlots();
  cancelBooking();
});
