// Consumer app orchestrator: ties geo -> radius search -> map -> slots -> booking,
// and keeps slots live via Supabase Realtime.
import { api, ApiError } from "./api.js";
import { store } from "./state.js";
import { getCurrentPosition, geocodeAddress } from "./geo.js";
import { renderMap, renderBarbershopMarkers, recenterMap } from "./map.js";
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
  searchInput:  () => document.getElementById("search-input"),
};

let unsubscribeSlots = null;
// Priority-3 fallback: Jerusalem city centre (used when GPS denied + no search).
const DEFAULT_POSITION = { lat: 31.7683, lng: 35.2137 };

// Client-side filter state (applied over the fetched shops, persists across searches).
const filterState = { maxDistanceM: null };

// Clear barbershop pins from the map between location changes (avoids pileup).
function clearMarkers() {
  const markers = store.get().markers;
  if (markers) markers.forEach((m) => m.setMap(null));
  store.set({ markers: [] });
}

// The shops currently visible after applying the active filter.
function visibleShops() {
  const all = store.get().barbershops || [];
  if (filterState.maxDistanceM == null) return all;
  return all.filter(
    (b) => b.distance_m == null || b.distance_m <= filterState.maxDistanceM
  );
}

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
      const { position } = store.get();
      renderMap(mapEl, position).then((map) => {
        store.set({ map });
        const shops = visibleShops();
        if (shops.length) {
          const markers = renderBarbershopMarkers(map, shops, selectBarbershop);
          store.set({ markers });
        }
      });
    }
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  // Priority on load: GPS -> Jerusalem fallback. (Manual search overrides later.)
  try {
    const position = await getCurrentPosition();
    await setLocation(position, { label: "מיקומך" });
  } catch {
    const banner = els.geoBanner();
    if (banner) banner.hidden = false;
    await setLocation(DEFAULT_POSITION, { label: "ירושלים" });
  }
}

// Single entry point for any location change (GPS, search, fallback).
// Updates state + label, re-fetches nearby shops, recenters the map.
async function setLocation(position, { label } = {}) {
  store.set({ position });
  if (label) {
    const el = els.locationLabel();
    if (el) el.textContent = label;
  }
  await loadNearby();

  // Follow the new location on the map if it's already rendered.
  if (store.get().map) {
    recenterMap(store.get().map, position);
  }
}

async function loadNearby() {
  const { position } = store.get();
  const barbershops = await api.nearbyBarbershops(position.lat, position.lng);
  store.set({ barbershops });
  renderShops();
}

// Render the currently-visible shops (post-filter) into the list + map.
function renderShops() {
  const shops = visibleShops();
  renderBarbershops(shops);

  const count = els.shopCount();
  if (count) count.textContent = `${shops.length} ספרים`;

  // Redraw markers if the map exists (clear old pins first to avoid pileup).
  if (store.get().map) {
    clearMarkers();
    const markers = renderBarbershopMarkers(store.get().map, shops, selectBarbershop);
    store.set({ markers });
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
      <div class="w-full flex flex-col items-center justify-center text-center py-12 px-gutter gap-3">
        <span class="material-symbols-outlined text-5xl text-surface-variant">location_off</span>
        <p class="font-headline-sm text-headline-sm text-text-primary">לא נמצאו ספרים באזור זה</p>
        <p class="font-body-md text-text-secondary text-sm">נסה לחפש עיר אחרת או להרחיב את הסינון</p>
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

// ── Manual location search ───────────────────────────────────────────────────

// Lazily-created inline hint shown under the search bar on geocode failure.
function searchHint(message) {
  const input = els.searchInput();
  if (!input) return;
  let hint = document.getElementById("search-hint");
  if (!hint) {
    hint = document.createElement("p");
    hint.id = "search-hint";
    hint.className = "px-gutter -mt-3 mb-3 text-danger font-body-md text-xs text-right";
    // Place it right after the search/filter row (input's grandparent).
    const row = input.closest(".flex");
    row?.parentElement?.insertBefore(hint, row.nextSibling);
  }
  hint.textContent = message || "";
  hint.classList.toggle("hidden", !message);
}

// Resolve the typed address -> geocode -> re-fetch + recenter.
// Empty query falls back to GPS (then Jerusalem if denied).
async function handleSearch() {
  const input = els.searchInput();
  const query = input?.value.trim();
  searchHint("");

  if (!query) {
    try {
      const position = await getCurrentPosition();
      await setLocation(position, { label: "מיקומך" });
    } catch {
      await setLocation(DEFAULT_POSITION, { label: "ירושלים" });
    }
    return;
  }

  try {
    const geo = await geocodeAddress(query);
    // Use the typed query as the short label (formatted_address is long).
    await setLocation({ lat: geo.lat, lng: geo.lng }, { label: query });
  } catch (err) {
    console.warn("Geocode failed:", err.message);
    searchHint("הכתובת לא נמצאה — נסה שוב");
  }
}

// ── Toast (non-blocking feedback) ────────────────────────────────────────────

let toastTimer = null;
function toast(message) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.className =
      "fixed left-1/2 -translate-x-1/2 bottom-28 z-[60] bg-surface-container " +
      "border border-border-light text-text-primary font-body-md text-sm " +
      "px-5 py-2.5 rounded-full shadow-2xl opacity-0 transition-opacity duration-200 pointer-events-none";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.remove("opacity-0");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("opacity-0"), 2000);
}

// ── Filter bottom-sheet (client-side distance filter) ────────────────────────

function ensureFilterSheet() {
  let backdrop = document.getElementById("filter-backdrop");
  if (backdrop) return backdrop;

  backdrop = document.createElement("div");
  backdrop.id = "filter-backdrop";
  backdrop.className =
    "fixed inset-0 z-[70] bg-black/60 opacity-0 pointer-events-none " +
    "transition-opacity duration-200 flex items-end justify-center";
  backdrop.innerHTML = `
    <div id="filter-sheet"
         class="w-full max-w-[430px] bg-surface-container border-t border-border-light
                rounded-t-3xl p-gutter pb-[calc(20px+env(safe-area-inset-bottom))]
                translate-y-full transition-transform duration-300 ease-out">
      <div class="w-10 h-1 bg-surface-variant rounded-full mx-auto mb-stack-lg"></div>
      <div class="flex justify-between items-center mb-stack-lg">
        <h2 class="font-headline-md text-headline-md">סינון</h2>
        <button id="filter-close" class="text-text-muted hover:text-text-primary transition-colors">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>
      <label class="font-body-md text-text-secondary text-sm flex justify-between mb-stack-sm">
        <span>מרחק מקסימלי</span>
        <span id="filter-distance-label" class="font-label-mono text-primary"></span>
      </label>
      <input id="filter-distance" type="range" min="500" max="10000" step="500"
             class="w-full accent-primary mb-stack-lg"/>
      <div class="flex gap-3">
        <button id="filter-reset"
                class="flex-1 py-3 rounded-xl border border-border-light text-text-primary font-body-lg
                       hover:bg-surface-2 transition-colors">איפוס</button>
        <button id="filter-apply"
                class="flex-1 py-3 rounded-xl bg-primary text-on-primary font-headline-sm
                       active:scale-95 transition-transform">החל</button>
      </div>
    </div>`;
  document.body.appendChild(backdrop);

  const slider = backdrop.querySelector("#filter-distance");
  const label = backdrop.querySelector("#filter-distance-label");
  const syncLabel = () => {
    const v = Number(slider.value);
    label.textContent = v >= 10000 ? "ללא הגבלה" : `${(v / 1000).toFixed(1)} ק"מ`;
  };
  slider.addEventListener("input", syncLabel);

  backdrop.querySelector("#filter-close").addEventListener("click", closeFilterSheet);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeFilterSheet();
  });
  backdrop.querySelector("#filter-reset").addEventListener("click", () => {
    filterState.maxDistanceM = null;
    slider.value = "10000";
    syncLabel();
    renderShops();
    closeFilterSheet();
    toast("הסינון אופס");
  });
  backdrop.querySelector("#filter-apply").addEventListener("click", () => {
    const v = Number(slider.value);
    filterState.maxDistanceM = v >= 10000 ? null : v;
    renderShops();
    closeFilterSheet();
    toast(`${visibleShops().length} תוצאות`);
  });

  return backdrop;
}

function openFilterSheet() {
  const backdrop = ensureFilterSheet();
  const sheet = backdrop.querySelector("#filter-sheet");
  const slider = backdrop.querySelector("#filter-distance");
  slider.value = String(filterState.maxDistanceM ?? 10000);
  slider.dispatchEvent(new Event("input"));
  backdrop.classList.remove("opacity-0", "pointer-events-none");
  requestAnimationFrame(() => sheet.classList.remove("translate-y-full"));
}

function closeFilterSheet() {
  const backdrop = document.getElementById("filter-backdrop");
  if (!backdrop) return;
  backdrop.querySelector("#filter-sheet").classList.add("translate-y-full");
  backdrop.classList.add("opacity-0", "pointer-events-none");
}

// ── Event wiring ─────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  // View toggle buttons.
  els.btnListView()?.addEventListener("click", () => setView("list"));
  els.btnMapView()?.addEventListener("click", () => setView("map"));

  // Manual location search: Enter in the field, or click the search icon.
  els.searchInput()?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSearch();
    }
  });
  document
    .querySelectorAll('.material-symbols-outlined')
    .forEach((icon) => {
      if (icon.textContent.trim() === "search") {
        icon.style.cursor = "pointer";
        icon.addEventListener("click", handleSearch);
      }
    });

  // Filter button (tune/filter_list icon) -> open the filter bottom-sheet.
  document.querySelectorAll(".material-symbols-outlined").forEach((icon) => {
    const name = icon.textContent.trim();
    if (name === "filter_list" || name === "tune") {
      const btn = icon.closest("button") || icon;
      btn.style.cursor = "pointer";
      btn.addEventListener("click", openFilterSheet);
    }
  });

  // Bottom nav: prevent dead "#" jumps; surface not-yet-built tabs cleanly.
  document.querySelectorAll("nav a").forEach((link) => {
    const label = link.textContent.trim();
    link.addEventListener("click", (e) => {
      e.preventDefault();
      if (label.includes("בית")) {
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else {
        toast("בקרוב 🚧");
      }
    });
  });

  // Close slots panel — also release any active pessimistic lock (no orphan locks).
  document.getElementById("btn-close-slots")?.addEventListener("click", () => {
    cancelBooking();
    els.lockTimerBar()?.classList.add("hidden");
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
