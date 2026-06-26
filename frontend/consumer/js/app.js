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
  viewHome:     () => document.getElementById("view-home"),
  viewBarber:   () => document.getElementById("view-barber"),
  viewSuccess:  () => document.getElementById("view-success"),
  viewBookings: () => document.getElementById("view-bookings"),
  viewProfile:  () => document.getElementById("view-profile"),
  viewSplash:   () => document.getElementById("view-splash"),
  viewRole:     () => document.getElementById("view-role"),
  viewVerify:   () => document.getElementById("view-verify"),
};

let unsubscribeSlots = null;
// Priority-3 fallback: Jerusalem city centre (used when GPS denied + no search).
const DEFAULT_POSITION = { lat: 31.7683, lng: 35.2137 };

// Client-side filter state (applied over the fetched shops, persists across searches).
const filterState = { maxDistanceM: null, openNow: false, serviceTypes: [] };

// Client-side text search query (filters loaded shops by name/address).
let searchQuery = "";

// Clear barbershop pins from the map between location changes (avoids pileup).
function clearMarkers() {
  const markers = store.get().markers;
  if (markers) markers.forEach((m) => m.setMap(null));
  store.set({ markers: [] });
}

// The shops currently visible after applying all active filters + search query.
function visibleShops() {
  let shops = store.get().barbershops || [];

  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    shops = shops.filter(
      (b) =>
        b.name?.toLowerCase().includes(q) ||
        b.address?.toLowerCase().includes(q)
    );
  }
  if (filterState.maxDistanceM != null) {
    shops = shops.filter(
      (b) => b.distance_m == null || b.distance_m <= filterState.maxDistanceM
    );
  }
  if (filterState.openNow) {
    shops = shops.filter((b) => b.opening_hours?.open_now === true);
  }
  if (filterState.serviceTypes.length > 0) {
    const serviceKeywords = {
      תספורת: ["תספורת", "תסרוקת", "קאט", "cut", "hair"],
      זקן:    ["זקן", "beard", "שפם"],
      ילדים:  ["ילדים", "ילד", "kids", "children"],
      צבע:    ["צבע", "color", "colour", "highlights"],
    };
    shops = shops.filter((b) =>
      filterState.serviceTypes.some((type) => {
        const kws = serviceKeywords[type] || [type];
        return kws.some((kw) => b.name?.toLowerCase().includes(kw.toLowerCase()));
      })
    );
  }
  return shops;
}

// ── View toggle (List ↔ Map) ─────────────────────────────────────────────────

function setView(view) {
  const isList = view === "list";
  if (isList) hideMapPreview();
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
          const markers = renderBarbershopMarkers(map, shops, showMapPreview);
          store.set({ markers });
        }
      });
    }
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  // First-run: send new visitors through onboarding before the home loads.
  if (!localStorage.getItem("torli_onboarded") && (!location.hash || location.hash === "#/home")) {
    location.hash = "#/splash";
  }

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
    const markers = renderBarbershopMarkers(store.get().map, shops, showMapPreview);
    store.set({ markers });
  }
}

// Floating barber preview card shown when a map pin is tapped (Stitch motif).
let mapPreviewShop = null;
function showMapPreview(shop) {
  mapPreviewShop = shop;
  const card = document.getElementById("map-preview");
  if (!card) return;
  document.getElementById("mp-name").textContent = shop.name;
  document.getElementById("mp-addr").textContent = shop.address || "";
  document.getElementById("mp-dist").textContent =
    shop.distance_m != null ? `${Math.round(shop.distance_m)} מ' ממך` : "";
  card.classList.remove("translate-y-[130%]", "opacity-0", "pointer-events-none");
  if (shop.lat != null && shop.lng != null && store.get().map) {
    store.get().map.panTo({ lat: shop.lat, lng: shop.lng });
  }
}
function hideMapPreview() {
  document
    .getElementById("map-preview")
    ?.classList.add("translate-y-[130%]", "opacity-0", "pointer-events-none");
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
  const slot = (store.get().slots || []).find((s) => s.id === slotId);
  const shop = store.get().selectedBarbershop;
  if (!slot || !shop) return;
  store.set({ pendingSlot: slot });

  try {
    await startBooking(slotId, {
      onTick: (remaining) => {
        const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
        const ss = String(remaining % 60).padStart(2, "0");
        const el = document.getElementById("cs-countdown");
        if (el) el.textContent = `${mm}:${ss}`;
      },
      onExpire: () => {
        closeConfirmSheet();
        toast("פג תוקף ההזמנה — בחר תור מחדש");
      },
    });
    openConfirmSheet(shop, slot);
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      toast("מצטערים, התור הזה כבר נתפס");
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
         class="min-w-[260px] bg-surface-2 rounded-[20px] overflow-hidden border border-border-light
                relative flex-shrink-0 cursor-pointer hover:border-primary/40 transition-colors group">
      <!-- Card photo: real image when available, gradient fallback otherwise -->
      <div class="h-32 w-full relative overflow-hidden ${b.photo_url ? "" : "photo-placeholder"}">
        ${b.photo_url
          ? `<img src="${b.photo_url}" alt="${b.name}" class="w-full h-full object-cover" loading="lazy" onerror="this.parentElement.classList.add('photo-placeholder');this.remove()">`
          : `<span class="material-symbols-outlined text-5xl text-primary/30 group-hover:scale-110 transition-transform duration-300 absolute inset-0 flex items-center justify-center">content_cut</span>`
        }
        <div class="absolute inset-0 card-gradient"></div>
        <!-- Barber avatar overlay (Stitch motif) -->
        <div class="absolute -bottom-5 right-4 z-10 w-12 h-12 rounded-full bg-surface-2 border-2 border-surface-2 gold-ring flex items-center justify-center">
          <span class="material-symbols-outlined text-primary text-[20px]" style="font-variation-settings:'FILL' 1;">storefront</span>
        </div>
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
      <div class="p-4 pt-6">
        <h3 class="font-headline-sm text-headline-sm text-right mb-0.5 truncate">${b.name}</h3>
        <p class="font-body-md text-text-secondary text-sm text-right truncate">${b.address || ""}</p>
        ${b.rating != null ? `
        <div class="mt-1.5 flex items-center justify-end gap-1">
          <span class="font-label-mono text-label-mono text-[11px] text-text-muted">(${b.rating_count ?? 0})</span>
          <span class="font-label-mono text-label-mono text-[11px] text-text-secondary">${b.rating.toFixed(1)}</span>
          <span class="material-symbols-outlined text-primary text-[14px]" style="font-variation-settings:'FILL' 1;">star</span>
        </div>` : ""}
        <div class="mt-3 flex justify-end">
          <span class="font-label-mono text-label-mono text-[11px] text-primary border border-primary/30 rounded-full px-3 py-1
                       group-hover:bg-primary group-hover:text-on-primary transition-colors">
            בחר תור ←
          </span>
        </div>
      </div>
    </div>`
    )
    .join("");

  list.querySelectorAll("[data-id]").forEach((el) => {
    const shop = barbershops.find((b) => b.id === el.dataset.id);
    el.addEventListener("click", () => {
      store.set({ selectedBarbershop: shop });
      location.hash = `#/barber/${shop.id}`;
    });
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

// ── Slot row (shared markup) ─────────────────────────────────────────────────

function slotRowHTML(s) {
  const time = new Date(s.slot_time).toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" });
  const date = new Date(s.slot_time).toLocaleDateString("he-IL", { weekday: "short", day: "numeric", month: "short" });
  return `
    <div data-id="${s.id}"
         class="bg-surface-1 border border-border-light rounded-2xl p-3 flex justify-between items-center
                cursor-pointer hover:bg-surface-2 hover:border-surface-variant transition-colors">
      <div class="flex flex-col items-center gap-0.5 w-16" dir="ltr">
        <span class="material-symbols-outlined text-primary text-[18px]">bolt</span>
        <span class="font-price-lg text-price-lg text-primary leading-none">${s.price != null ? "₪" + s.price : ""}</span>
      </div>
      <div class="flex-1 text-right flex flex-col justify-center pr-3">
        <span class="font-headline-sm text-base">${s.service_name}</span>
        <span class="font-body-md text-text-secondary text-xs mt-0.5">${time} · ${date}</span>
      </div>
      <span class="material-symbols-outlined text-text-muted">chevron_left</span>
    </div>`;
}

function wireSlotTaps(container) {
  container.querySelectorAll("[data-id]").forEach((el) =>
    el.addEventListener("click", () => bookSlot(el.dataset.id))
  );
}

// ── Router (hash-based) ──────────────────────────────────────────────────────

const VIEW_IDS = [
  "view-home", "view-barber", "view-success", "view-bookings", "view-profile",
  "view-splash", "view-role", "view-verify",
];
const ONBOARDING_VIEWS = ["view-splash", "view-role", "view-verify"];

function showView(id) {
  VIEW_IDS.forEach((v) => document.getElementById(v)?.classList.toggle("hidden", v !== id));
  // Hide bottom nav during onboarding (full-screen flow).
  document.getElementById("bottom-nav")?.classList.toggle("hidden", ONBOARDING_VIEWS.includes(id));
  // Active nav state.
  const route = id === "view-home" ? "#/home" : id === "view-bookings" ? "#/bookings" : id === "view-profile" ? "#/profile" : null;
  document.querySelectorAll(".nav-link").forEach((a) => {
    const on = a.dataset.route === route;
    a.classList.toggle("text-primary", on);
    a.classList.toggle("scale-110", on);
    a.classList.toggle("text-text-muted", !on);
  });
  window.scrollTo({ top: 0 });
}

async function router() {
  const hash = location.hash || "#/home";
  const barberMatch = hash.match(/^#\/barber\/(.+)$/);

  if (barberMatch) {
    showView("view-barber");
    await renderBarberView(barberMatch[1]);
  } else if (hash.startsWith("#/bookings")) {
    showView("view-bookings");
    renderBookingsView();
  } else if (hash.startsWith("#/profile")) {
    showView("view-profile");
    renderProfileView();
  } else if (hash.startsWith("#/success")) {
    showView("view-success");
    renderSuccessView();
  } else if (hash.startsWith("#/splash")) {
    showView("view-splash");
    renderSplashView();
  } else if (hash.startsWith("#/role")) {
    showView("view-role");
    renderRoleView();
  } else if (hash.startsWith("#/verify")) {
    showView("view-verify");
    renderVerifyView();
  } else {
    showView("view-home");
  }
}

// ── View: Barber Profile ─────────────────────────────────────────────────────

async function renderBarberView(shopId) {
  const view = els.viewBarber();
  let shop = store.get().selectedBarbershop;
  if (!shop || shop.id !== shopId) {
    try { shop = await api.getBarbershop(shopId); store.set({ selectedBarbershop: shop }); }
    catch { view.innerHTML = `<p class="p-gutter text-text-muted">לא נמצא</p>`; return; }
  }

  view.innerHTML = `
    <!-- Hero -->
    <section class="relative w-full h-[240px]">
      <div class="w-full h-full ${shop.photo_url ? "" : "photo-placeholder"} flex items-center justify-center overflow-hidden">
        ${shop.photo_url
          ? `<img src="${shop.photo_url}" alt="${shop.name}" class="w-full h-full object-cover" loading="eager" onerror="this.parentElement.classList.add('photo-placeholder');this.remove()">`
          : `<span class="material-symbols-outlined text-7xl text-primary/25">content_cut</span>`
        }
      </div>
      <div class="absolute inset-0" style="background:linear-gradient(to bottom,rgba(19,19,21,.2),#131315)"></div>
      <button id="bp-back" class="absolute top-4 right-4 w-10 h-10 rounded-full bg-surface-1/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-text-primary">
        <span class="material-symbols-outlined">arrow_forward</span>
      </button>
      <div class="absolute bottom-0 right-gutter translate-y-1/2">
        <div class="w-24 h-24 rounded-full border-2 border-primary overflow-hidden bg-surface-2 flex items-center justify-center shadow-[0_0_15px_rgba(239,178,0,0.15)]">
          ${shop.photo_url
            ? `<img src="${shop.photo_url}" alt="${shop.name}" class="w-full h-full object-cover">`
            : `<span class="material-symbols-outlined text-4xl text-primary" style="font-variation-settings:'FILL' 1;">storefront</span>`
          }
        </div>
      </div>
    </section>

    <!-- Info -->
    <section class="px-gutter pt-16 pb-stack-lg">
      <h1 class="font-headline-lg-mobile text-headline-lg-mobile text-text-primary">${shop.name}</h1>
      <p class="font-body-md text-body-md text-text-secondary mt-1">${shop.address || ""}</p>
      <div class="flex items-center gap-stack-md mt-stack-sm flex-wrap">
        ${shop.distance_m != null ? `
        <div class="flex items-center gap-1 text-text-secondary">
          <span class="material-symbols-outlined text-[18px]">location_on</span>
          <span class="font-body-md text-body-md">${Math.round(shop.distance_m)} מ'</span>
        </div>` : ""}
        ${shop.rating != null ? `
        <div class="flex items-center gap-1">
          <span class="material-symbols-outlined text-primary text-[18px]" style="font-variation-settings:'FILL' 1;">star</span>
          <span class="font-body-md text-body-md text-text-primary">${shop.rating.toFixed(1)}</span>
          <span class="font-body-md text-body-md text-text-secondary">(${shop.rating_count ?? 0})</span>
        </div>` : ""}
      </div>
      <div class="flex gap-stack-sm mt-stack-lg">
        ${shop.phone ? `
        <a href="tel:${shop.phone}" class="flex-1 h-12 rounded-lg bg-surface-2 border border-border-light flex items-center justify-center gap-2 hover:bg-surface-3 transition-colors">
          <span class="material-symbols-outlined text-[20px]">call</span>
          <span class="font-body-md text-body-md font-medium">התקשר</span>
        </a>` : ""}
        ${shop.booking_url ? `
        <a href="${shop.booking_url}" target="_blank" rel="noopener" class="flex-1 h-12 rounded-lg bg-surface-2 border border-border-light flex items-center justify-center gap-2 hover:bg-surface-3 transition-colors">
          <span class="material-symbols-outlined text-[20px]">public</span>
          <span class="font-body-md text-body-md font-medium">אתר</span>
        </a>` : ""}
      </div>
    </section>

    <!-- Tabs -->
    <div class="border-b border-border-light sticky top-0 bg-background/90 backdrop-blur-xl z-30">
      <div class="flex px-gutter">
        <button data-tab="services" class="bp-tab flex-1 py-4 text-center font-body-md text-body-md">שירותים</button>
        <button data-tab="portfolio" class="bp-tab flex-1 py-4 text-center font-body-md text-body-md">תיק עבודות</button>
        <button data-tab="reviews" class="bp-tab flex-1 py-4 text-center font-body-md text-body-md">חוות דעת</button>
      </div>
    </div>

    <!-- Tab: Services (slots) — default -->
    <section id="bp-services" class="px-gutter py-stack-lg">
      <div id="bp-slots" class="flex flex-col gap-3">
        <div class="h-16 bg-surface-2 rounded-2xl border border-border-light animate-pulse"></div>
        <div class="h-16 bg-surface-2 rounded-2xl border border-border-light animate-pulse"></div>
      </div>
    </section>

    <!-- Tab: Portfolio — real photos from photo_urls, gradient fallback for empty slots -->
    <section id="bp-portfolio" class="p-gutter grid grid-cols-3 gap-1 hidden">
      ${Array.from({ length: 9 }).map((_, i) => {
        const urls = shop.photo_urls || [];
        const url = urls[i] || null;
        return url
          ? `<div class="aspect-square rounded-sm overflow-hidden">
               <img src="${url}" alt="${shop.name}" class="w-full h-full object-cover" loading="lazy"
                    onerror="this.parentElement.classList.add('photo-placeholder','flex','items-center','justify-center');this.remove()">
             </div>`
          : `<div class="aspect-square rounded-sm photo-placeholder flex items-center justify-center">
               <span class="material-symbols-outlined text-primary/20 text-2xl">content_cut</span>
             </div>`;
      }).join("")}
    </section>

    <!-- Tab: Reviews — Google rating summary + CTA -->
    <section id="bp-reviews" class="px-gutter py-section-gap hidden">
      ${shop.rating != null ? `
      <div class="bg-surface-1 border border-border-light rounded-2xl p-stack-lg mb-stack-lg text-center">
        <p class="font-price-lg text-price-lg text-primary drop-shadow-[0_0_8px_rgba(239,178,0,0.3)]">${shop.rating.toFixed(1)}</p>
        <div class="flex items-center justify-center gap-0.5 my-stack-sm">
          ${Array.from({ length: 5 }).map((_, i) => {
            const filled = i < Math.round(shop.rating);
            return `<span class="material-symbols-outlined text-primary text-[20px]" style="font-variation-settings:'FILL' ${filled ? 1 : 0};">star</span>`;
          }).join("")}
        </div>
        <p class="font-body-md text-body-md text-text-secondary">מבוסס על ${shop.rating_count ?? 0} חוות דעת בגוגל</p>
      </div>` : ""}
      <div class="flex flex-col items-center justify-center text-center gap-3 py-6">
        <span class="material-symbols-outlined text-5xl text-surface-variant">rate_review</span>
        <p class="font-body-lg text-body-lg text-text-secondary">שתף את החוויה שלך</p>
        <p class="font-body-md text-text-muted text-sm">לאחר התור תוכל לדרג את הספר</p>
      </div>
    </section>`;

  document.getElementById("bp-back").addEventListener("click", () => { location.hash = "#/home"; });

  // Tabs.
  const tabPanels = { services: "bp-services", portfolio: "bp-portfolio", reviews: "bp-reviews" };
  const setTab = (name) => {
    Object.entries(tabPanels).forEach(([t, id]) =>
      document.getElementById(id)?.classList.toggle("hidden", t !== name)
    );
    view.querySelectorAll(".bp-tab").forEach((b) => {
      const on = b.dataset.tab === name;
      b.classList.toggle("text-primary", on);
      b.classList.toggle("font-bold", on);
      b.classList.toggle("border-b-2", on);
      b.classList.toggle("border-primary", on);
      b.classList.toggle("text-text-secondary", !on);
    });
  };
  view.querySelectorAll(".bp-tab").forEach((b) =>
    b.addEventListener("click", () => setTab(b.dataset.tab))
  );
  setTab("services");

  // Load slots (real) + live updates into the Services tab.
  const fill = (slots) => {
    store.set({ slots });
    const box = document.getElementById("bp-slots");
    if (!box) return;
    box.innerHTML = slots.length
      ? slots.map(slotRowHTML).join("")
      : `<p class="text-text-muted font-body-md py-6 text-center">אין תורים פנויים כרגע</p>`;
    wireSlotTaps(box);
  };
  fill(await api.listSlots(shop.id));
  if (unsubscribeSlots) unsubscribeSlots();
  unsubscribeSlots = subscribeToSlots({
    barbershopId: shop.id,
    onChange: () => api.listSlots(shop.id).then(fill),
  });
}

// ── View: Booking Success ────────────────────────────────────────────────────

function renderSuccessView() {
  const b = store.get().lastBooking;
  const view = els.viewSuccess();
  if (!b) { location.hash = "#/home"; return; }
  const d = new Date(b.slot.slot_time);
  view.innerHTML = `
    <main class="px-gutter py-section-gap min-h-screen flex flex-col">
      <div class="mt-8"></div>
      <div class="flex justify-center items-center w-full mb-stack-lg relative">
        <div class="absolute w-32 h-32 bg-primary/20 rounded-full blur-2xl"></div>
        <div class="w-24 h-24 rounded-full bg-surface-1 border border-primary/30 flex items-center justify-center relative z-10 shadow-[0_0_30px_rgba(239,178,0,0.15)]">
          <span class="material-symbols-outlined text-[56px] text-primary" style="font-variation-settings:'FILL' 1;">check_circle</span>
        </div>
      </div>
      <div class="text-center mb-section-gap flex flex-col items-center">
        <h1 class="font-display-lg text-display-lg text-text-primary mb-stack-sm">שריינת!</h1>
        <p class="font-body-lg text-body-lg text-text-secondary">נתראה אצל ${b.shop.name} ב-${d.toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" })}</p>
      </div>
      <div class="bg-surface-1 rounded-xl p-stack-lg border border-primary/30 shadow-[0_8px_32px_rgba(239,178,0,0.1)] flex flex-col gap-stack-md">
        ${successRow("content_cut", "שירות", b.slot.service_name)}
        <div class="h-px w-full bg-border-light"></div>
        ${successRow("calendar_today", "תאריך", d.toLocaleDateString("he-IL", { day: "numeric", month: "long", year: "numeric" }))}
        <div class="h-px w-full bg-border-light"></div>
        ${successRow("schedule", "שעה", d.toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" }))}
      </div>
      <div class="flex-grow min-h-[32px]"></div>
      <button id="bs-home" class="w-full bg-text-primary text-background py-4 rounded-xl font-headline-sm text-headline-sm active:scale-[0.98] transition-all">
        חזרה לדף הבית
      </button>
    </main>`;
  document.getElementById("bs-home").addEventListener("click", () => { location.hash = "#/home"; });
}

function successRow(icon, label, value) {
  return `
    <div class="flex items-center gap-4">
      <div class="w-12 h-12 rounded-full bg-surface-2 flex items-center justify-center text-primary shrink-0 border border-border-light">
        <span class="material-symbols-outlined">${icon}</span>
      </div>
      <div class="flex flex-col">
        <span class="font-label-mono text-label-mono text-text-secondary mb-1">${label}</span>
        <span class="font-headline-sm text-headline-sm text-text-primary">${value}</span>
      </div>
    </div>`;
}

// ── View: My Bookings + Profile (placeholders pending bookings-history API) ───

function placeholderView(view, icon, title, sub) {
  view.innerHTML = `
    <header class="px-gutter pt-8 pb-4"><h1 class="font-headline-lg text-headline-lg">${title}</h1></header>
    <div class="flex flex-col items-center justify-center text-center gap-3 px-gutter" style="min-height:60vh">
      <span class="material-symbols-outlined text-6xl text-surface-variant">${icon}</span>
      <p class="font-body-lg text-body-lg text-text-secondary">${sub}</p>
    </div>`;
}

async function renderBookingsView() {
  const view = els.viewBookings();
  view.innerHTML = `
    <header class="px-gutter pt-8 pb-4"><h1 class="font-headline-lg text-headline-lg">התורים שלי</h1></header>
    <div id="mb-list" class="px-gutter flex flex-col gap-3">
      <div class="h-20 bg-surface-2 rounded-2xl border border-border-light animate-pulse"></div>
      <div class="h-20 bg-surface-2 rounded-2xl border border-border-light animate-pulse"></div>
    </div>`;

  let bookings = [];
  try {
    bookings = await api.listBookings(store.get().userToken);
  } catch (err) {
    console.error("listBookings failed:", err);
  }

  const box = document.getElementById("mb-list");
  if (!box) return;
  if (!bookings.length) {
    box.innerHTML = `
      <div class="flex flex-col items-center justify-center text-center gap-3 py-16">
        <span class="material-symbols-outlined text-6xl text-surface-variant">event_busy</span>
        <p class="font-body-lg text-body-lg text-text-secondary">עדיין אין לך תורים</p>
        <a href="#/home" class="font-label-mono text-label-mono text-primary border border-primary/30 rounded-full px-4 py-1.5">מצא ספר ←</a>
      </div>`;
    return;
  }

  const now = Date.now();
  box.innerHTML = bookings
    .map((b) => {
      const d = new Date(b.slot_time);
      const cancelled = b.status === "cancelled";
      const upcoming = !cancelled && d.getTime() >= now;
      const chip = cancelled
        ? `<span class="font-label-mono text-label-mono text-[10px] px-2 py-1 rounded-full bg-error-container/20 text-error border border-error/20">מבוטל</span>`
        : `<span class="font-label-mono text-label-mono text-[10px] px-2 py-1 rounded-full ${upcoming ? "bg-primary/10 text-primary border border-primary/30" : "bg-surface-3 text-text-muted"}">${upcoming ? "מתוכנן" : "עבר"}</span>`;
      return `
      <div class="bg-surface-1 border ${upcoming ? "border-primary/30" : "border-border-light"} rounded-2xl p-stack-md ${cancelled ? "opacity-60" : ""}">
        <div class="flex items-center gap-stack-md">
          <div class="w-12 h-12 rounded-full bg-surface-2 border border-border-light flex items-center justify-center text-primary shrink-0">
            <span class="material-symbols-outlined">content_cut</span>
          </div>
          <div class="flex-1 text-right min-w-0">
            <p class="font-headline-sm text-base truncate">${b.shop_name}</p>
            <p class="font-body-md text-text-secondary text-sm truncate">${b.service_name}${b.price != null ? " · ₪" + b.price : ""}</p>
            <p class="font-label-mono text-label-mono text-text-muted text-[11px] mt-0.5">
              ${d.toLocaleDateString("he-IL", { day: "numeric", month: "short" })} · ${d.toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" })}
            </p>
          </div>
          ${chip}
        </div>
        ${upcoming ? `
        <button data-cancel-id="${b.booking_id}"
                class="mt-stack-md w-full h-10 rounded-lg border border-error/30 text-error font-body-md text-sm
                       hover:bg-error-container/10 transition-colors">
          בטל תור
        </button>` : ""}
      </div>`;
    })
    .join("");

  box.querySelectorAll("[data-cancel-id]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const ok = await confirmDialog("ביטול תור", "לבטל את התור? לא ניתן לשחזר.", "בטל תור");
      if (!ok) return;
      try {
        await api.cancelBooking(btn.dataset.cancelId, store.get().userToken);
        toast("התור בוטל");
        renderBookingsView();
      } catch (err) {
        console.error(err);
        toast("ביטול נכשל — נסה שוב");
      }
    })
  );
}

// Styled yes/no confirm dialog. Returns a Promise<boolean>.
function confirmDialog(title, body, confirmLabel = "אישור") {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className =
      "fixed inset-0 z-[90] bg-black/60 flex items-end justify-center opacity-0 transition-opacity duration-200";
    backdrop.innerHTML = `
      <div class="confirm-card w-full max-w-[430px] bg-surface-1 border-t border-border-light rounded-t-3xl
                  p-gutter pb-[calc(20px+env(safe-area-inset-bottom))] translate-y-full transition-transform duration-300 ease-out">
        <div class="w-10 h-1 bg-surface-variant rounded-full mx-auto mb-stack-lg"></div>
        <h2 class="font-headline-md text-headline-md mb-stack-sm">${title}</h2>
        <p class="font-body-md text-body-md text-text-secondary mb-stack-lg">${body}</p>
        <div class="flex gap-3">
          <button data-act="no" class="flex-1 py-3 rounded-xl border border-border-light text-text-primary font-body-lg hover:bg-surface-2 transition-colors">חזרה</button>
          <button data-act="yes" class="flex-1 py-3 rounded-xl bg-error text-on-error font-headline-sm active:scale-95 transition-transform">${confirmLabel}</button>
        </div>
      </div>`;
    document.body.appendChild(backdrop);
    const card = backdrop.querySelector(".confirm-card");
    requestAnimationFrame(() => {
      backdrop.classList.remove("opacity-0");
      card.classList.remove("translate-y-full");
    });
    const close = (val) => {
      card.classList.add("translate-y-full");
      backdrop.classList.add("opacity-0");
      setTimeout(() => backdrop.remove(), 250);
      resolve(val);
    };
    backdrop.querySelector('[data-act="yes"]').addEventListener("click", () => close(true));
    backdrop.querySelector('[data-act="no"]').addEventListener("click", () => close(false));
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(false); });
  });
}

async function renderProfileView() {
  const view = els.viewProfile();
  const name = localStorage.getItem("torli_customer_name") || "אורח";
  const phone = localStorage.getItem("torli_customer_phone") || "";

  const row = (icon, label, attrs = "") => `
    <button ${attrs} class="w-full flex items-center gap-stack-md p-stack-md bg-surface-1 border border-border-light rounded-xl hover:bg-surface-2 transition-colors">
      <span class="material-symbols-outlined text-text-secondary">${icon}</span>
      <span class="flex-1 text-right font-body-md text-body-md text-text-primary">${label}</span>
      <span class="material-symbols-outlined text-text-muted">chevron_left</span>
    </button>`;

  view.innerHTML = `
    <header class="px-gutter pt-8 pb-4"><h1 class="font-headline-lg text-headline-lg">פרופיל</h1></header>

    <!-- Identity card -->
    <section class="px-gutter mb-section-gap">
      <div class="bg-surface-1 border border-border-light rounded-2xl p-stack-lg flex items-center gap-stack-md">
        <div class="w-16 h-16 rounded-full bg-surface-2 border border-primary/40 flex items-center justify-center text-primary shrink-0">
          <span class="material-symbols-outlined text-3xl" style="font-variation-settings:'FILL' 1;">person</span>
        </div>
        <div class="flex-1 text-right min-w-0">
          <p id="pf-name" class="font-headline-sm text-headline-sm truncate">${name}</p>
          <p id="pf-phone" class="font-body-md text-text-secondary text-sm truncate">${phone || "אין מספר טלפון"}</p>
        </div>
        <button id="pf-edit" class="w-10 h-10 rounded-full bg-surface-2 border border-border-light flex items-center justify-center text-primary hover:bg-surface-3 transition-colors">
          <span class="material-symbols-outlined text-[20px]">edit</span>
        </button>
      </div>
      <!-- Inline edit (hidden) -->
      <div id="pf-edit-form" class="hidden mt-stack-md flex flex-col gap-stack-sm">
        <input id="pf-name-input" placeholder="שם מלא" value="${name === "אורח" ? "" : name}"
               class="w-full bg-surface-2 border border-border-light rounded-lg h-12 px-4 font-body-md text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/50"/>
        <input id="pf-phone-input" type="tel" placeholder="מספר טלפון" value="${phone}"
               class="w-full bg-surface-2 border border-border-light rounded-lg h-12 px-4 font-body-md text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/50"/>
        <button id="pf-save" class="w-full bg-primary text-on-primary font-headline-sm text-headline-sm py-3 rounded-xl active:scale-95 transition-transform">שמור</button>
      </div>
    </section>

    <!-- Stat -->
    <section class="px-gutter mb-section-gap">
      <div class="bg-surface-1 border border-border-light rounded-2xl p-stack-lg flex items-center justify-between">
        <span class="font-body-md text-body-md text-text-secondary">סך התורים שלי</span>
        <span id="pf-count" class="font-price-lg text-price-lg text-primary">—</span>
      </div>
    </section>

    <!-- Settings -->
    <section class="px-gutter flex flex-col gap-stack-sm">
      ${row("favorite", "המועדפים שלי", 'id="pf-bookings"')}
      ${row("history", "תורים קודמים", 'id="pf-past-bookings"')}
      ${row("language", "שפה · עברית", 'id="pf-lang"')}
      ${row("notifications", "התראות", 'id="pf-notif"')}
      ${row("help", "עזרה ותמיכה", 'id="pf-help"')}
    </section>`;

  // Edit toggle + save.
  document.getElementById("pf-edit").addEventListener("click", () =>
    document.getElementById("pf-edit-form").classList.toggle("hidden")
  );
  document.getElementById("pf-save").addEventListener("click", () => {
    const n = document.getElementById("pf-name-input").value.trim();
    const p = document.getElementById("pf-phone-input").value.trim();
    if (n) localStorage.setItem("torli_customer_name", n);
    if (p) localStorage.setItem("torli_customer_phone", p);
    document.getElementById("pf-name").textContent = n || "אורח";
    document.getElementById("pf-phone").textContent = p || "אין מספר טלפון";
    document.getElementById("pf-edit-form").classList.add("hidden");
    toast("הפרטים נשמרו");
  });

  // Row actions.
  document.getElementById("pf-bookings").addEventListener("click", () => toast("המועדפים בקרוב"));
  document.getElementById("pf-past-bookings").addEventListener("click", () => { location.hash = "#/bookings"; });
  document.getElementById("pf-lang").addEventListener("click", () => openProfileSheet("language"));
  document.getElementById("pf-notif").addEventListener("click", () => openProfileSheet("notifications"));
  document.getElementById("pf-help").addEventListener("click", () => openProfileSheet("help"));

  // Bookings count.
  try {
    const bookings = await api.listBookings(store.get().userToken);
    const c = document.getElementById("pf-count");
    if (c) c.textContent = String(bookings.length);
  } catch { /* leave dash */ }
}

// ── Onboarding: Splash / Role / Verify (UI flow; no auth backend) ────────────

function renderSplashView() {
  els.viewSplash().innerHTML = `
    <main class="min-h-screen flex flex-col items-center justify-between px-gutter py-section-gap text-center">
      <div class="flex-grow flex flex-col items-center justify-center gap-stack-lg">
        <div class="relative">
          <div class="absolute inset-0 bg-primary/20 rounded-full blur-2xl"></div>
          <div class="relative w-24 h-24 rounded-full bg-surface-1 border border-primary/30 flex items-center justify-center shadow-[0_0_30px_rgba(239,178,0,0.15)]">
            <span class="material-symbols-outlined text-5xl text-primary" style="font-variation-settings:'FILL' 1;">content_cut</span>
          </div>
        </div>
        <div>
          <h1 class="font-display-lg text-display-lg text-text-primary">Tor</h1>
          <p class="font-body-lg text-body-lg text-text-secondary mt-stack-sm">הזמנת תורים מהירה למספרות פרימיום</p>
        </div>
      </div>
      <div class="w-full">
        <button id="sp-start" class="w-full bg-primary text-on-primary font-headline-sm text-headline-sm py-4 rounded-xl active:scale-[0.98] transition-transform flex items-center justify-center gap-2">
          מתחילים <span class="material-symbols-outlined">arrow_back</span>
        </button>
        <p class="font-label-mono text-label-mono text-text-muted text-[11px] mt-stack-md">v 1.0.0</p>
      </div>
    </main>`;
  document.getElementById("sp-start").addEventListener("click", () => { location.hash = "#/role"; });
}

function renderRoleView() {
  els.viewRole().innerHTML = `
    <main class="min-h-screen flex flex-col px-gutter py-section-gap">
      <button id="rl-back" class="w-10 h-10 rounded-full bg-surface-2 border border-border-light flex items-center justify-center text-text-primary mb-section-gap">
        <span class="material-symbols-outlined">arrow_forward</span>
      </button>
      <h1 class="font-headline-lg-mobile text-headline-lg-mobile text-text-primary mb-stack-sm">ברוכים הבאים ל-Tor</h1>
      <p class="font-body-md text-body-md text-text-secondary mb-section-gap">אנא בחרו את סוג המשתמש שלכם כדי שנוכל להתאים את החוויה עבורכם.</p>
      <div class="flex flex-col gap-stack-md">
        <button id="rl-customer" class="text-right bg-surface-1 border border-primary/30 rounded-2xl p-stack-lg flex items-center gap-stack-md hover:border-primary transition-colors gold-ring">
          <div class="w-12 h-12 rounded-full bg-surface-2 flex items-center justify-center text-primary shrink-0">
            <span class="material-symbols-outlined">content_cut</span>
          </div>
          <div class="flex-1">
            <p class="font-headline-sm text-headline-sm">אני לקוח</p>
            <p class="font-body-md text-text-secondary text-sm">חיפוש והזמנת תורים למספרות</p>
          </div>
          <span class="material-symbols-outlined text-primary">chevron_left</span>
        </button>
        <button id="rl-barber" class="text-right bg-surface-1 border border-border-light rounded-2xl p-stack-lg flex items-center gap-stack-md hover:border-surface-variant transition-colors">
          <div class="w-12 h-12 rounded-full bg-surface-2 flex items-center justify-center text-text-secondary shrink-0">
            <span class="material-symbols-outlined">calendar_month</span>
          </div>
          <div class="flex-1">
            <p class="font-headline-sm text-headline-sm">אני ספר / בעל עסק</p>
            <p class="font-body-md text-text-secondary text-sm">ניהול יומן, לקוחות והעסק שלי</p>
          </div>
          <span class="material-symbols-outlined text-text-muted">chevron_left</span>
        </button>
      </div>
    </main>`;
  document.getElementById("rl-back").addEventListener("click", () => { location.hash = "#/splash"; });
  document.getElementById("rl-customer").addEventListener("click", () => { location.hash = "#/verify"; });
  document.getElementById("rl-barber").addEventListener("click", () => toast("אפליקציית הספרים בקרוב 🚧"));
}

function renderVerifyView() {
  const view = els.viewVerify();
  const phonePrefill = localStorage.getItem("torli_customer_phone") || "";

  // Step 1 — phone entry.
  const phoneStep = () => {
    view.innerHTML = `
      <main class="min-h-screen flex flex-col px-gutter py-section-gap">
        <button id="vf-back" class="w-10 h-10 rounded-full bg-surface-2 border border-border-light flex items-center justify-center text-text-primary mb-section-gap">
          <span class="material-symbols-outlined">arrow_forward</span>
        </button>
        <h1 class="font-headline-lg-mobile text-headline-lg-mobile mb-stack-sm">מה מספר הטלפון שלך?</h1>
        <p class="font-body-md text-body-md text-text-secondary mb-section-gap">נשלח קוד אימות חד-פעמי ב-SMS.</p>
        <input id="vf-phone" type="tel" inputmode="tel" placeholder="05X-XXXXXXX" value="${phonePrefill}"
               class="w-full bg-surface-1 border border-border-light rounded-xl h-14 px-4 text-center font-price-lg text-price-lg tracking-widest text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/50"/>
        <div class="flex-grow"></div>
        <button id="vf-send" class="w-full bg-primary text-on-primary font-headline-sm text-headline-sm py-4 rounded-xl active:scale-[0.98] transition-transform">שלח קוד</button>
      </main>`;
    document.getElementById("vf-back").addEventListener("click", () => { location.hash = "#/role"; });
    document.getElementById("vf-send").addEventListener("click", () => {
      const phone = document.getElementById("vf-phone").value.trim();
      if (!phone) { toast("הזן מספר טלפון"); return; }
      localStorage.setItem("torli_customer_phone", phone);
      otpStep(phone);
    });
  };

  // Step 2 — OTP (mock: any 4 digits confirm).
  const otpStep = (phone) => {
    view.innerHTML = `
      <main class="min-h-screen flex flex-col px-gutter py-section-gap">
        <button id="vf-back2" class="w-10 h-10 rounded-full bg-surface-2 border border-border-light flex items-center justify-center text-text-primary mb-section-gap">
          <span class="material-symbols-outlined">arrow_forward</span>
        </button>
        <h1 class="font-headline-lg-mobile text-headline-lg-mobile mb-stack-sm">אימות מספר טלפון</h1>
        <p class="font-body-md text-body-md text-text-secondary mb-section-gap">שלחנו קוד ל-${phone}</p>
        <div dir="ltr" class="flex justify-center gap-3 mb-stack-lg">
          ${[0,1,2,3].map(() => `
            <input class="vf-otp w-14 h-16 bg-surface-1 border border-border-light rounded-xl text-center font-price-lg text-price-lg text-text-primary focus:outline-none focus:border-primary" maxlength="1" inputmode="numeric"/>`).join("")}
        </div>
        <button id="vf-resend" class="font-label-mono text-label-mono text-primary text-sm mx-auto mb-section-gap">שלח שוב</button>
        <div class="flex-grow"></div>
        <button id="vf-confirm" class="w-full bg-primary text-on-primary font-headline-sm text-headline-sm py-4 rounded-xl active:scale-[0.98] transition-transform">אמת והמשך</button>
        <p class="font-label-mono text-label-mono text-text-muted text-[10px] text-center mt-stack-sm">דמו: כל קוד בן 4 ספרות יתקבל</p>
      </main>`;
    document.getElementById("vf-back2").addEventListener("click", phoneStep);
    document.getElementById("vf-resend").addEventListener("click", () => toast("קוד נשלח שוב"));
    const otps = [...view.querySelectorAll(".vf-otp")];
    otps.forEach((inp, i) => {
      inp.addEventListener("input", () => { if (inp.value && i < 3) otps[i + 1].focus(); });
      inp.addEventListener("keydown", (e) => { if (e.key === "Backspace" && !inp.value && i > 0) otps[i - 1].focus(); });
    });
    otps[0].focus();
    document.getElementById("vf-confirm").addEventListener("click", () => {
      const code = otps.map((o) => o.value).join("");
      if (code.length < 4) { toast("הזן קוד בן 4 ספרות"); return; }
      localStorage.setItem("torli_onboarded", "1");
      toast("ברוך הבא! 🎉");
      location.hash = "#/home";
    });
  };

  phoneStep();
}

// ── Search: client-side filter by name/address ───────────────────────────────

function handleSearch() {
  const input = els.searchInput();
  searchQuery = input?.value.trim() ?? "";
  renderShops(visibleShops());
}

// ── Location city picker ──────────────────────────────────────────────────────

const CITY_LIST = [
  { name: "תל אביב",       lat: 32.0853, lng: 34.7818 },
  { name: "ירושלים",      lat: 31.7683, lng: 35.2137 },
  { name: "חיפה",          lat: 32.7940, lng: 34.9896 },
  { name: "באר שבע",      lat: 31.2518, lng: 34.7913 },
  { name: "ראשון לציון", lat: 31.9730, lng: 34.7925 },
  { name: "אשדוד",         lat: 31.8040, lng: 34.6550 },
  { name: "נתניה",         lat: 32.3215, lng: 34.8532 },
  { name: "אילת",          lat: 29.5577, lng: 34.9519 },
];

function openLocationSheet() {
  let backdrop = document.getElementById("location-backdrop");
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.id = "location-backdrop";
    backdrop.className =
      "fixed inset-0 z-[70] bg-black/60 flex items-end justify-center " +
      "transition-opacity duration-200";
    const cities = CITY_LIST.map((c) => `
      <button data-lat="${c.lat}" data-lng="${c.lng}" data-name="${c.name}"
              class="loc-city w-full flex items-center gap-stack-md p-stack-md rounded-xl hover:bg-surface-2 transition-colors text-right">
        <span class="material-symbols-outlined text-primary" style="font-variation-settings:'FILL' 1;">location_city</span>
        <span class="font-body-md text-body-md text-text-primary">${c.name}</span>
      </button>`).join("");
    backdrop.innerHTML = `
      <div id="location-sheet"
           class="w-full max-w-[430px] bg-surface-container border-t border-border-light
                  rounded-t-3xl p-gutter pb-[calc(20px+env(safe-area-inset-bottom))]
                  translate-y-full transition-transform duration-300 ease-out">
        <div class="w-10 h-1 bg-surface-variant rounded-full mx-auto mb-stack-lg"></div>
        <div class="flex justify-between items-center mb-stack-lg">
          <h2 class="font-headline-md text-headline-md">בחר עיר</h2>
          <button id="loc-close"><span class="material-symbols-outlined text-text-muted">close</span></button>
        </div>
        <button id="loc-gps"
                class="w-full flex items-center gap-stack-md p-stack-md rounded-xl bg-primary/10 border border-primary/30 mb-stack-md hover:bg-primary/20 transition-colors text-right">
          <span class="material-symbols-outlined text-primary" style="font-variation-settings:'FILL' 1;">my_location</span>
          <span class="font-body-md font-medium text-primary">השתמש במיקום שלי</span>
        </button>
        <div class="flex flex-col gap-1">${cities}</div>
      </div>`;
    document.body.appendChild(backdrop);

    const sheet = backdrop.querySelector("#location-sheet");
    const close = () => {
      sheet.classList.add("translate-y-full");
      backdrop.classList.add("opacity-0", "pointer-events-none");
    };
    backdrop.querySelector("#loc-close").addEventListener("click", close);
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });

    backdrop.querySelector("#loc-gps").addEventListener("click", async () => {
      close();
      try {
        const pos = await getCurrentPosition();
        await setLocation(pos, { label: "מיקומך" });
      } catch {
        await setLocation(DEFAULT_POSITION, { label: "ירושלים" });
      }
    });
    backdrop.querySelectorAll(".loc-city").forEach((btn) => {
      btn.addEventListener("click", async () => {
        close();
        const lat = parseFloat(btn.dataset.lat);
        const lng = parseFloat(btn.dataset.lng);
        await setLocation({ lat, lng }, { label: btn.dataset.name });
      });
    });
  }

  const sheet = backdrop.querySelector("#location-sheet");
  backdrop.classList.remove("opacity-0", "pointer-events-none");
  requestAnimationFrame(() => sheet.classList.remove("translate-y-full"));
}

// ── Profile action sheets ─────────────────────────────────────────────────────

function openProfileSheet(type) {
  const id = `profile-sheet-${type}`;
  let backdrop = document.getElementById(`${id}-backdrop`);
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.id = `${id}-backdrop`;
    backdrop.className =
      "fixed inset-0 z-[70] bg-black/60 flex items-end justify-center " +
      "transition-opacity duration-200";

    const contents = {
      language: `
        <h2 class="font-headline-md text-headline-md mb-stack-lg">שפה</h2>
        <div class="flex flex-col gap-stack-sm">
          <button class="w-full flex items-center justify-between p-stack-md rounded-xl bg-primary/10 border border-primary/30">
            <span class="font-body-md text-primary font-medium">עברית</span>
            <span class="material-symbols-outlined text-primary">check_circle</span>
          </button>
          <button class="w-full flex items-center justify-between p-stack-md rounded-xl bg-surface-2 border border-border-light opacity-50">
            <span class="font-body-md text-text-secondary">English</span>
            <span class="font-label-mono text-label-mono text-text-muted text-xs">בקרוב</span>
          </button>
          <button class="w-full flex items-center justify-between p-stack-md rounded-xl bg-surface-2 border border-border-light opacity-50">
            <span class="font-body-md text-text-secondary">العربية</span>
            <span class="font-label-mono text-label-mono text-text-muted text-xs">בקרוב</span>
          </button>
        </div>`,
      notifications: `
        <h2 class="font-headline-md text-headline-md mb-stack-lg">התראות</h2>
        <div class="flex flex-col gap-stack-sm">
          <div class="flex items-center justify-between p-stack-md rounded-xl bg-surface-2 border border-border-light">
            <span class="font-body-md text-text-primary">תזכורות לתורים</span>
            <button onclick="event.currentTarget.classList.toggle('bg-primary');event.currentTarget.classList.toggle('bg-surface-3')"
                    class="w-12 h-6 rounded-full bg-surface-3 transition-colors relative">
              <span class="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform"></span>
            </button>
          </div>
          <div class="flex items-center justify-between p-stack-md rounded-xl bg-surface-2 border border-border-light">
            <span class="font-body-md text-text-primary">מבצעים מיוחדים</span>
            <button onclick="event.currentTarget.classList.toggle('bg-primary');event.currentTarget.classList.toggle('bg-surface-3')"
                    class="w-12 h-6 rounded-full bg-surface-3 transition-colors relative">
              <span class="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform"></span>
            </button>
          </div>
          <p class="font-label-mono text-label-mono text-text-muted text-xs text-center pt-2">שליחת הודעות SMS בקרוב</p>
        </div>`,
      help: `
        <h2 class="font-headline-md text-headline-md mb-stack-lg">עזרה ותמיכה</h2>
        <div class="flex flex-col gap-stack-sm">
          <a href="https://wa.me/972500000000" target="_blank" rel="noopener"
             class="w-full flex items-center gap-stack-md p-stack-md rounded-xl bg-surface-2 border border-border-light hover:bg-surface-3 transition-colors">
            <span class="material-symbols-outlined text-primary">chat</span>
            <div class="text-right">
              <p class="font-body-md text-text-primary">WhatsApp</p>
              <p class="font-label-mono text-label-mono text-text-muted text-xs">זמין א׳-ה׳ 9:00-18:00</p>
            </div>
          </a>
          <a href="mailto:support@torli.app"
             class="w-full flex items-center gap-stack-md p-stack-md rounded-xl bg-surface-2 border border-border-light hover:bg-surface-3 transition-colors">
            <span class="material-symbols-outlined text-primary">mail</span>
            <div class="text-right">
              <p class="font-body-md text-text-primary">מייל</p>
              <p class="font-label-mono text-label-mono text-text-muted text-xs">support@torli.app</p>
            </div>
          </a>
        </div>`,
    };

    backdrop.innerHTML = `
      <div id="${id}-sheet"
           class="w-full max-w-[430px] bg-surface-container border-t border-border-light
                  rounded-t-3xl p-gutter pb-[calc(20px+env(safe-area-inset-bottom))]
                  translate-y-full transition-transform duration-300 ease-out">
        <div class="w-10 h-1 bg-surface-variant rounded-full mx-auto mb-stack-lg"></div>
        ${contents[type] || ""}
        <button id="${id}-close" class="mt-stack-lg w-full py-3 rounded-xl border border-border-light text-text-secondary font-body-md">סגור</button>
      </div>`;
    document.body.appendChild(backdrop);

    const sheet = backdrop.querySelector(`#${id}-sheet`);
    const close = () => {
      sheet.classList.add("translate-y-full");
      backdrop.classList.add("opacity-0", "pointer-events-none");
    };
    backdrop.querySelector(`#${id}-close`).addEventListener("click", close);
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
  }

  const sheet = backdrop.querySelector(`#${id}-sheet`);
  backdrop.classList.remove("opacity-0", "pointer-events-none");
  requestAnimationFrame(() => sheet.classList.remove("translate-y-full"));
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
  const serviceChips = ["תספורת", "זקן", "ילדים", "צבע"].map((s) =>
    `<button data-svc="${s}"
             class="svc-chip px-4 py-2 rounded-full border border-border-light font-body-md text-sm
                    text-text-secondary hover:border-primary/50 transition-colors">${s}</button>`
  ).join("");

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

      <!-- Open Now toggle -->
      <div class="flex items-center justify-between mb-stack-lg">
        <span class="font-body-md text-text-primary">פתוח עכשיו</span>
        <button id="filter-open-now"
                class="w-12 h-6 rounded-full transition-colors relative ${filterState.openNow ? "bg-primary" : "bg-surface-3"}">
          <span class="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all duration-200 ${filterState.openNow ? "left-[calc(100%-22px)]" : "left-0.5"}"></span>
        </button>
      </div>

      <!-- Service type chips -->
      <p class="font-body-md text-text-secondary text-sm mb-stack-sm">סוג שירות</p>
      <div class="flex flex-wrap gap-2 mb-stack-lg">${serviceChips}</div>

      <!-- Distance slider -->
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

  // Open Now toggle.
  let openNowLocal = filterState.openNow;
  const openNowBtn = backdrop.querySelector("#filter-open-now");
  const syncOpenNow = () => {
    openNowBtn.classList.toggle("bg-primary", openNowLocal);
    openNowBtn.classList.toggle("bg-surface-3", !openNowLocal);
    const dot = openNowBtn.querySelector("span");
    if (dot) {
      dot.classList.toggle("left-[calc(100%-22px)]", openNowLocal);
      dot.classList.toggle("left-0.5", !openNowLocal);
    }
  };
  openNowBtn.addEventListener("click", () => { openNowLocal = !openNowLocal; syncOpenNow(); });

  // Service chips toggle.
  let selectedServices = [...filterState.serviceTypes];
  backdrop.querySelectorAll(".svc-chip").forEach((chip) => {
    const svc = chip.dataset.svc;
    if (selectedServices.includes(svc)) {
      chip.classList.add("border-primary", "text-primary", "bg-primary/10");
    }
    chip.addEventListener("click", () => {
      const idx = selectedServices.indexOf(svc);
      if (idx === -1) {
        selectedServices.push(svc);
        chip.classList.add("border-primary", "text-primary", "bg-primary/10");
      } else {
        selectedServices.splice(idx, 1);
        chip.classList.remove("border-primary", "text-primary", "bg-primary/10");
      }
    });
  });

  backdrop.querySelector("#filter-close").addEventListener("click", closeFilterSheet);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeFilterSheet();
  });
  backdrop.querySelector("#filter-reset").addEventListener("click", () => {
    filterState.maxDistanceM = null;
    filterState.openNow = false;
    filterState.serviceTypes = [];
    openNowLocal = false;
    selectedServices = [];
    syncOpenNow();
    backdrop.querySelectorAll(".svc-chip").forEach((c) =>
      c.classList.remove("border-primary", "text-primary", "bg-primary/10")
    );
    slider.value = "10000";
    syncLabel();
    renderShops(visibleShops());
    closeFilterSheet();
    toast("הסינון אופס");
  });
  backdrop.querySelector("#filter-apply").addEventListener("click", () => {
    const v = Number(slider.value);
    filterState.maxDistanceM = v >= 10000 ? null : v;
    filterState.openNow = openNowLocal;
    filterState.serviceTypes = [...selectedServices];
    renderShops(visibleShops());
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

// ── Confirm & Pay bottom-sheet (Stitch frame "אישור ותשלום") ─────────────────

const PAY_METHODS = [
  { value: "pay_at_shop", icon: "storefront", label: "שלם במספרה", sub: "הבטחת התור באמצעות פרטים" },
  { value: "apple_pay", icon: "apps", label: "Apple Pay", sub: null },
  { value: "credit_card", icon: "credit_card", label: "כרטיס אשראי חדש", sub: null },
];

function buildConfirmSheet() {
  let backdrop = document.getElementById("confirm-backdrop");
  if (backdrop) return backdrop;

  backdrop = document.createElement("div");
  backdrop.id = "confirm-backdrop";
  backdrop.className =
    "fixed inset-0 z-[80] bg-black/60 opacity-0 pointer-events-none " +
    "transition-opacity duration-200 flex items-end justify-center";

  const methods = PAY_METHODS.map(
    (m, i) => `
    <label class="block cursor-pointer">
      <input class="cs-pay sr-only" name="cs_pay" type="radio" value="${m.value}" ${i === 0 ? "checked" : ""}/>
      <div class="cs-pay-card bg-surface-2 border border-border-light rounded-lg p-stack-md flex items-center gap-stack-md transition-all">
        <div class="w-10 h-6 bg-surface-3 rounded flex items-center justify-center border border-border-light">
          <span class="material-symbols-outlined text-text-muted text-[18px]">${m.icon}</span>
        </div>
        <div class="flex-1">
          <p class="text-body-md font-body-md text-text-primary">${m.label}</p>
          ${m.sub ? `<p class="text-label-mono font-label-mono text-text-muted text-[11px]">${m.sub}</p>` : ""}
        </div>
        <div class="cs-check w-6 h-6 rounded-full bg-primary flex items-center justify-center opacity-0 scale-50 transition-all duration-300">
          <span class="material-symbols-outlined text-on-primary text-sm">check</span>
        </div>
      </div>
    </label>`
  ).join("");

  backdrop.innerHTML = `
    <div id="confirm-sheet"
         class="w-full max-w-[430px] bg-surface-1 border-t border-border-light rounded-t-3xl
                max-h-[92vh] overflow-y-auto hide-scrollbar translate-y-full
                transition-transform duration-300 ease-out">
      <div class="sticky top-0 bg-surface-1 pt-3 pb-2 z-10">
        <div class="w-10 h-1 bg-surface-variant rounded-full mx-auto"></div>
      </div>
      <div class="px-gutter pb-3 flex justify-between items-center">
        <h2 class="font-headline-md text-headline-md">אישור ותשלום</h2>
        <button id="cs-close" class="text-text-muted hover:text-text-primary transition-colors">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <div class="px-gutter flex flex-col gap-stack-lg pb-4">
        <!-- Order summary -->
        <section class="bg-surface-2 rounded-xl p-stack-md border border-border-light">
          <h3 class="text-label-mono font-label-mono text-text-muted mb-stack-sm">סיכום הזמנה</h3>
          <div class="flex items-center gap-stack-sm mb-stack-md pb-stack-md border-b border-border-light">
            <div class="w-12 h-12 rounded-full bg-surface-3 border border-border-light flex items-center justify-center text-primary">
              <span class="material-symbols-outlined" style="font-variation-settings:'FILL' 1;">content_cut</span>
            </div>
            <div class="text-right flex-1 min-w-0">
              <p id="cs-shop" class="text-body-lg font-body-lg text-text-primary truncate"></p>
              <p id="cs-addr" class="text-body-md font-body-md text-text-muted truncate"></p>
            </div>
          </div>
          <div class="space-y-stack-sm mb-stack-md">
            <div class="flex justify-between items-center">
              <span class="text-body-md font-body-md text-text-muted">שירות</span>
              <span id="cs-service" class="text-body-md font-body-md text-text-primary"></span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-body-md font-body-md text-text-muted">תאריך ושעה</span>
              <span id="cs-time" class="text-body-md font-body-md text-text-primary"></span>
            </div>
          </div>
          <div class="flex justify-between items-center pt-stack-sm border-t border-border-light">
            <span class="text-body-lg font-body-lg text-text-primary">סה"כ</span>
            <span id="cs-total" class="text-price-lg font-price-lg text-primary drop-shadow-[0_0_8px_rgba(239,178,0,0.3)]"></span>
          </div>
        </section>

        <!-- Customer details (required by booking API; not shown in Stitch which assumes auth) -->
        <section class="flex flex-col gap-stack-sm">
          <h3 class="text-label-mono font-label-mono text-text-muted">פרטי לקוח</h3>
          <input id="cs-name" placeholder="שם מלא" required
                 class="w-full bg-surface-2 border border-border-light rounded-lg h-12 px-4 font-body-md text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/50 transition-colors"/>
          <input id="cs-phone" type="tel" placeholder="מספר טלפון" required
                 class="w-full bg-surface-2 border border-border-light rounded-lg h-12 px-4 font-body-md text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/50 transition-colors"/>
        </section>

        <!-- Payment methods -->
        <section>
          <h3 class="text-label-mono font-label-mono text-text-muted mb-stack-sm">אמצעי תשלום</h3>
          <div class="space-y-stack-sm">${methods}</div>
        </section>

        <!-- No-show protection -->
        <section class="bg-surface-2 border border-border-light rounded-lg p-stack-md flex gap-stack-sm items-start">
          <span class="material-symbols-outlined text-primary mt-0.5">shield_lock</span>
          <div>
            <p class="text-body-md font-body-md text-text-primary mb-1">הגנה מפני אי-הגעה</p>
            <p class="text-label-mono font-label-mono text-text-muted text-[11px] leading-relaxed">הפרטים נשמרים בצורה מאובטחת לביטחון התור בלבד. חיוב יבוצע רק במקרה של אי-הגעה בהתאם למדיניות הביטול.</p>
          </div>
        </section>
        <!-- Cancellation policy -->
        <section class="bg-error-container/10 border border-error/20 rounded-lg p-stack-md flex gap-stack-sm items-start">
          <span class="material-symbols-outlined text-error mt-0.5" style="font-variation-settings:'FILL' 1;">warning</span>
          <div>
            <p class="text-body-md font-body-md text-error mb-1">מדיניות ביטולים</p>
            <p class="text-label-mono font-label-mono text-text-muted text-[11px] leading-relaxed">ביטול אפשרי עד שעתיים לפני התור. אי הגעה תחויב בדמי ביטול של ₪40.</p>
          </div>
        </section>
      </div>

      <!-- Sticky action -->
      <div class="sticky bottom-0 bg-surface-1/95 backdrop-blur-xl border-t border-border-light p-gutter pb-[calc(16px+env(safe-area-inset-bottom))]">
        <div class="flex items-center justify-center gap-2 bg-primary-container/10 border border-primary-container/30 py-2 px-4 rounded-full mb-stack-md animate-pulse">
          <span class="material-symbols-outlined text-primary-container text-sm">timer</span>
          <span class="font-label-mono text-label-mono text-primary-container text-xs">התור ננעל עבורך</span>
          <span id="cs-countdown" class="font-label-mono text-label-mono text-primary-container text-xs font-bold mr-auto">--:--</span>
        </div>
        <label class="flex items-center gap-stack-sm mb-stack-md cursor-pointer">
          <input id="cs-terms" type="checkbox"
                 class="w-5 h-5 rounded border-border-light bg-surface-3 text-primary focus:ring-primary"/>
          <span class="text-label-mono font-label-mono text-text-muted text-[11px]">אני מסכים/ה לתנאי השימוש ולמדיניות הביטולים.</span>
        </label>
        <button id="cs-confirm" disabled
                class="w-full bg-text-primary text-black h-14 rounded-xl text-body-lg font-body-lg font-bold
                       enabled:hover:opacity-90 enabled:active:scale-[0.98] transition-all duration-200
                       flex justify-center items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed">
          <span>אשר תור</span><span class="opacity-30 px-1">·</span><span id="cs-cta-price"></span>
        </button>
      </div>
    </div>`;
  document.body.appendChild(backdrop);

  // Payment radio gold-check toggle.
  backdrop.querySelectorAll(".cs-pay").forEach((radio) => {
    radio.addEventListener("change", () => {
      backdrop.querySelectorAll("label").forEach((lbl) => {
        const r = lbl.querySelector(".cs-pay");
        const card = lbl.querySelector(".cs-pay-card");
        const check = lbl.querySelector(".cs-check");
        if (!r || !card || !check) return;
        const on = r.checked;
        card.classList.toggle("border-primary", on);
        check.classList.toggle("opacity-0", !on);
        check.classList.toggle("scale-50", !on);
      });
    });
  });

  // CTA gating: terms + name + phone.
  const gate = () => {
    const ok =
      backdrop.querySelector("#cs-terms").checked &&
      backdrop.querySelector("#cs-name").value.trim() &&
      backdrop.querySelector("#cs-phone").value.trim();
    backdrop.querySelector("#cs-confirm").disabled = !ok;
  };
  ["#cs-terms", "#cs-name", "#cs-phone"].forEach((sel) =>
    backdrop.querySelector(sel).addEventListener("input", gate)
  );

  backdrop.querySelector("#cs-close").addEventListener("click", () => {
    cancelBooking();
    closeConfirmSheet();
  });
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) {
      cancelBooking();
      closeConfirmSheet();
    }
  });
  backdrop.querySelector("#cs-confirm").addEventListener("click", onConfirmBooking);

  // Trigger initial check styling for the default-selected method.
  backdrop.querySelector(".cs-pay").dispatchEvent(new Event("change"));
  return backdrop;
}

function openConfirmSheet(shop, slot) {
  const backdrop = buildConfirmSheet();
  const $ = (s) => backdrop.querySelector(s);

  $("#cs-shop").textContent = shop.name;
  $("#cs-addr").textContent = shop.address || "";
  $("#cs-service").textContent = slot.service_name;
  $("#cs-time").textContent = new Date(slot.slot_time).toLocaleString("he-IL", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
  const price = slot.price != null ? `₪${slot.price}` : "—";
  $("#cs-total").textContent = price;
  $("#cs-cta-price").textContent = price;

  // Prefill saved customer details.
  $("#cs-name").value = localStorage.getItem("torli_customer_name") || "";
  $("#cs-phone").value = localStorage.getItem("torli_customer_phone") || "";
  $("#cs-terms").checked = false;
  $("#cs-confirm").disabled = true;

  backdrop.classList.remove("opacity-0", "pointer-events-none");
  requestAnimationFrame(() => $("#confirm-sheet").classList.remove("translate-y-full"));
}

function closeConfirmSheet() {
  const backdrop = document.getElementById("confirm-backdrop");
  if (!backdrop) return;
  backdrop.querySelector("#confirm-sheet").classList.add("translate-y-full");
  backdrop.classList.add("opacity-0", "pointer-events-none");
}

async function onConfirmBooking() {
  const backdrop = document.getElementById("confirm-backdrop");
  const name = backdrop.querySelector("#cs-name").value.trim();
  const phone = backdrop.querySelector("#cs-phone").value.trim();
  const btn = backdrop.querySelector("#cs-confirm");

  localStorage.setItem("torli_customer_name", name);
  localStorage.setItem("torli_customer_phone", phone);

  btn.disabled = true;
  btn.querySelector("span").textContent = "מאשר...";
  try {
    const result = await confirmBooking(name, phone);
    if (result.success) {
      store.set({
        lastBooking: { shop: store.get().selectedBarbershop, slot: store.get().pendingSlot },
      });
      closeConfirmSheet();
      location.hash = "#/success";
    } else {
      toast(`שגיאה: ${result.message || "נסה שוב"}`);
      btn.disabled = false;
      btn.querySelector("span").textContent = "אשר תור";
    }
  } catch (err) {
    console.error(err);
    toast("ההזמנה נכשלה — נסה שוב");
    btn.disabled = false;
    btn.querySelector("span").textContent = "אשר תור";
  }
}

// ── Event wiring ─────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  // View toggle buttons.
  els.btnListView()?.addEventListener("click", () => setView("list"));
  els.btnMapView()?.addEventListener("click", () => setView("map"));

  // Search: live client-side filter by shop name/address.
  els.searchInput()?.addEventListener("input", handleSearch);

  // Location picker: tap the location label to open the city picker.
  document.getElementById("location-btn")?.addEventListener("click", openLocationSheet);

  // Filter button (tune/filter_list icon) -> open the filter bottom-sheet.
  document.querySelectorAll(".material-symbols-outlined").forEach((icon) => {
    const name = icon.textContent.trim();
    if (name === "filter_list" || name === "tune") {
      const btn = icon.closest("button") || icon;
      btn.style.cursor = "pointer";
      btn.addEventListener("click", openFilterSheet);
    }
  });

  // Map preview "show slots" -> barber profile.
  document.getElementById("mp-go")?.addEventListener("click", () => {
    if (!mapPreviewShop) return;
    store.set({ selectedBarbershop: mapPreviewShop });
    location.hash = `#/barber/${mapPreviewShop.id}`;
  });

  // Hash router: nav links + deep links + back/forward all flow through here.
  window.addEventListener("hashchange", router);

  init().then(router);
});

window.addEventListener("beforeunload", () => {
  if (unsubscribeSlots) unsubscribeSlots();
  cancelBooking();
});
