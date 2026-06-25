// Consumer app orchestrator: ties geo -> radius search -> map -> slots -> booking,
// and keeps slots live via Supabase Realtime.
import { api, ApiError } from "./api.js";
import { store } from "./state.js";
import { getCurrentPosition } from "./geo.js";
import { renderMap, renderBarbershopMarkers } from "./map.js";
import { subscribeToSlots } from "./realtime.js";
import { startBooking, confirmBooking, cancelBooking } from "./booking.js";

// --- DOM hooks ---
const els = {
  map:          () => document.getElementById("map"),
  shopList:     () => document.getElementById("barbershop-list"),
  slotList:     () => document.getElementById("slot-list"),
  lockTimer:    () => document.getElementById("lock-timer"),
  lockTimerBar: () => document.getElementById("lock-timer-bar"),
  bookingForm:  () => document.getElementById("booking-form"),
  bookingSection:()=> document.getElementById("booking-section"),
  slotsSection: () => document.getElementById("slots-section"),
  slotsTitle:   () => document.getElementById("slots-title"),
  shopCount:    () => document.getElementById("shop-count"),
  locationLabel:() => document.getElementById("location-label"),
  geoBanner:    () => document.getElementById("geo-banner"),
  listPanel:    () => document.getElementById("list-panel"),
  mapPanel:     () => document.getElementById("map-panel"),
  btnListView:  () => document.getElementById("btn-list-view"),
  btnMapView:   () => document.getElementById("btn-map-view"),
};

let unsubscribeSlots = null;
const DEFAULT_POSITION = { lat: 32.0853, lng: 34.7818 };

// ── View toggle (List ↔ Map) ─────────────────────────────────────────────────

function setView(view) {
  const isList = view === "list";
  els.listPanel()?.classList.toggle("hidden", !isList);
  els.mapPanel()?.classList.toggle("hidden", isList);
  els.btnListView()?.classList.toggle("bg-surface-variant", isList);
  els.btnListView()?.classList.toggle("text-text-primary", isList);
  els.btnListView()?.classList.toggle("text-text-secondary", !isList);
  els.btnMapView()?.classList.toggle("bg-surface-variant", !isList);
  els.btnMapView()?.classList.toggle("text-text-primary", !isList);
  els.btnMapView()?.classList.toggle("text-text-secondary", isList);

  // Lazy-render the map the first time we switch to map view.
  if (!isList && !store.get().map) {
    const mapEl = els.map();
    if (mapEl) {
      const { position, barbershops } = store.get();
      renderMap(mapEl, position).then((map) => {
        store.set({ map });
        if (barbershops?.length) {
          renderBarbershopMarkers(map, barbershops, selectBarbershop);
        }
      });
    }
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  let position;
  try {
    position = await getCurrentPosition();
    const label = els.locationLabel();
    if (label) label.textContent = "מיקומך";
  } catch {
    position = DEFAULT_POSITION;
    const banner = els.geoBanner();
    if (banner) banner.hidden = false;
    const label = els.locationLabel();
    if (label) label.textContent = "תל אביב";
  }

  store.set({ position });
  await loadNearby();
}

async function loadNearby() {
  const { position } = store.get();
  const barbershops = await api.nearbyBarbershops(position.lat, position.lng);
  store.set({ barbershops });
  renderBarbershops(barbershops);

  const count = els.shopCount();
  if (count) count.textContent = `${barbershops.length} ספרים`;

  // If map is already visible, add markers immediately.
  if (store.get().map) {
    renderBarbershopMarkers(store.get().map, barbershops, selectBarbershop);
  }
}

async function selectBarbershop(shop) {
  store.set({ selectedBarbershop: shop });

  // Highlight selected card.
  els.shopList()?.querySelectorAll("[data-id]").forEach((el) => {
    el.classList.toggle("border-primary/50", el.dataset.id === shop.id);
    el.classList.toggle("border-border-light", el.dataset.id !== shop.id);
  });

  // Update slots section header.
  const title = els.slotsTitle();
  if (title) title.textContent = shop.name;

  const slots = await api.listSlots(shop.id);
  store.set({ slots });
  renderSlots(slots);

  // Live updates via Realtime.
  if (unsubscribeSlots) unsubscribeSlots();
  unsubscribeSlots = subscribeToSlots({
    barbershopId: shop.id,
    onChange: () => api.listSlots(shop.id).then(renderSlots),
  });

  // Scroll slots section into view.
  els.slotsSection()?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function bookSlot(slotId) {
  try {
    await startBooking(slotId, {
      onTick: (remaining) => {
        const t = els.lockTimer();
        if (t) t.textContent = `${remaining}s`;
        els.lockTimerBar()?.classList.remove("hidden");
      },
      onExpire: () => {
        alert("פג תוקף ההזמנה — אנא בחר תור מחדש.");
        els.lockTimerBar()?.classList.add("hidden");
        els.bookingSection()?.classList.add("hidden");
      },
    });
    els.bookingSection()?.classList.remove("hidden");
    els.bookingSection()?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      alert("מצטערים, התור הזה כבר נתפס.");
    } else {
      console.error(err);
    }
  }
}

// ── Renderers ────────────────────────────────────────────────────────────────

function renderBarbershops(barbershops) {
  const list = els.shopList();
  if (!list) return;

  if (!barbershops.length) {
    list.innerHTML = `
      <div class="px-gutter text-text-muted font-body-md py-8 text-center w-full">
        לא נמצאו ספרים בקרבתך
      </div>`;
    return;
  }

  list.innerHTML = barbershops
    .map(
      (b) => `
    <div data-id="${b.id}"
         class="min-w-[240px] bg-surface-2 rounded-[20px] overflow-hidden border border-border-light
                relative flex-shrink-0 cursor-pointer hover:border-surface-variant transition-colors group">
      <!-- Photo placeholder -->
      <div class="h-32 w-full bg-surface-3 flex items-center justify-center relative overflow-hidden">
        <span class="material-symbols-outlined text-5xl text-surface-variant group-hover:scale-110 transition-transform duration-300">content_cut</span>
        <div class="absolute inset-0 card-gradient"></div>
        ${
          b.distance_m != null
            ? `<div class="absolute top-3 left-3 bg-black/40 backdrop-blur-md border border-white/10
                          rounded-full px-2.5 py-1 flex items-center gap-1">
                 <span class="material-symbols-outlined text-primary text-[12px]" style="font-variation-settings:'FILL' 1;">location_on</span>
                 <span class="font-label-mono text-label-mono text-[11px]">${Math.round(b.distance_m)}מ'</span>
               </div>`
            : ""
        }
      </div>
      <!-- Info -->
      <div class="p-4">
        <h3 class="font-headline-sm text-headline-sm text-right mb-0.5 truncate">${b.name}</h3>
        <p class="font-body-md text-text-secondary text-sm text-right truncate">${b.address || ""}</p>
        <div class="mt-3 flex justify-end">
          <span class="font-label-mono text-label-mono text-[11px] text-primary border border-primary/30 rounded-full px-2 py-0.5">
            בחר תור ←
          </span>
        </div>
      </div>
    </div>`
    )
    .join("");

  list.querySelectorAll("[data-id]").forEach((el) => {
    const shop = barbershops.find((b) => b.id === el.dataset.id);
    el.addEventListener("click", () => selectBarbershop(shop));
  });
}

function renderSlots(slots) {
  const list = els.slotList();
  const section = els.slotsSection();
  if (!list) return;

  section?.classList.toggle("hidden", slots.length === 0);

  if (!slots.length) {
    list.innerHTML = "";
    return;
  }

  list.innerHTML = slots
    .map(
      (s) => `
    <div data-id="${s.id}"
         class="bg-surface-1 border border-border-light rounded-2xl p-3
                flex justify-between items-center cursor-pointer
                hover:bg-surface-2 hover:border-surface-variant transition-colors">
      <!-- Price / bolt -->
      <div class="flex flex-col items-center gap-0.5 w-16" dir="ltr">
        <span class="material-symbols-outlined text-primary text-[18px]">bolt</span>
        <span class="font-price-lg text-price-lg text-primary leading-none">
          ${s.price != null ? "₪" + s.price : ""}
        </span>
      </div>
      <!-- Time + service -->
      <div class="flex-1 text-right flex flex-col justify-center pr-3">
        <span class="font-headline-sm text-base">${s.service_name}</span>
        <span class="font-body-md text-text-secondary text-xs mt-0.5">
          ${new Date(s.slot_time).toLocaleTimeString("he-IL", {
            hour: "2-digit",
            minute: "2-digit",
          })}
          ·
          ${new Date(s.slot_time).toLocaleDateString("he-IL", {
            weekday: "short",
            day: "numeric",
            month: "short",
          })}
        </span>
      </div>
      <!-- Arrow -->
      <span class="material-symbols-outlined text-text-muted group-hover:text-primary transition-colors">
        chevron_left
      </span>
    </div>`
    )
    .join("");

  list.querySelectorAll("[data-id]").forEach((el) => {
    el.addEventListener("click", () => bookSlot(el.dataset.id));
  });
}

// ── Event wiring ─────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  // View toggle buttons.
  els.btnListView()?.addEventListener("click", () => setView("list"));
  els.btnMapView()?.addEventListener("click", () => setView("map"));

  // Close slots panel.
  document.getElementById("btn-close-slots")?.addEventListener("click", () => {
    els.slotsSection()?.classList.add("hidden");
    els.bookingSection()?.classList.add("hidden");
  });

  // Booking form submit.
  els.bookingForm()?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = new FormData(e.target);
    try {
      const result = await confirmBooking(data.get("name"), data.get("phone"));
      if (result.success) {
        alert("ההזמנה בוצעה בהצלחה! 🎉");
        els.bookingSection()?.classList.add("hidden");
        els.slotsSection()?.classList.add("hidden");
        els.lockTimerBar()?.classList.add("hidden");
      } else {
        alert(`שגיאה: ${result.message}`);
      }
    } catch (err) {
      console.error(err);
    }
  });

  init();
});

window.addEventListener("beforeunload", () => {
  if (unsubscribeSlots) unsubscribeSlots();
  cancelBooking();
});
