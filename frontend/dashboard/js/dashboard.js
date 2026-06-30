// Barber dashboard — 5 tabs (Stitch _14/_23/_3/_18/_41) over live owner data.
import {
  html, useState, useEffect, useMemo, useRef, Icon, Btn, Field, AppBar, BottomNav, FAB, Modal,
  Spinner, toast, waLink, fmtTime, ymd,
} from "./ui.js";
import * as data from "./data.js";
import * as auth from "./auth.js";

// Effective price of a slot: the deal price when it's a live deal, else the
// regular price. Bookings carry no price of their own — every money figure on
// the dashboard derives from the joined slot — so deal pricing resolves here.
function slotPrice(slot) {
  if (!slot) return null;
  return slot.is_deal && slot.deal_price != null ? slot.deal_price : slot.price;
}

const TABS = [
  { key: "calendar", label: "לוח", icon: "calendar_month" },
  { key: "loyalty", label: "לקוחות", icon: "loyalty" },
  { key: "stats", label: "סטטיסטיקות", icon: "equalizer" },
  { key: "staff", label: "עובדים", icon: "group" },
  { key: "services", label: "שירותים", icon: "content_cut" },
  { key: "settings", label: "הגדרות", icon: "settings" },
];

export function Dashboard({ shop, onSignOut, onShopUpdated }) {
  const [tab, setTab] = useState("calendar");
  const [appts, setAppts] = useState([]);
  const [slots, setSlots] = useState([]);
  const [services, setServices] = useState([]);
  const [staff, setStaff] = useState([]);
  const [overrides, setOverrides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [unseenList, setUnseenList] = useState([]); // new bookings since last seen
  const [notifOpen, setNotifOpen] = useState(false); // bell dropdown

  const seenIds = useRef(new Set());
  const prevStatus = useRef(new Map()); // booking id -> last-seen status, to detect cancellations
  const firstLoad = useRef(true);

  // Load everything; on ANY failure stop the spinner and surface the reason
  // (never leave the dashboard stuck loading). Also detects NEW bookings since
  // the last load to drive the alert toast + header badge.
  const reload = async () => {
    try {
      const [a, sl, sv, st, ov] = await Promise.all([
        data.listAppointments(),
        data.listSlots(shop.id),
        data.listServices(shop.id),
        data.listStaff(shop.id),
        data.listOverrides(shop.id),
      ]);
      // Alert on bookings that are new since a previous load (not the first one),
      // and on existing bookings whose status flipped to cancelled.
      const fresh = a.filter((b) => !seenIds.current.has(b.id));
      const justCancelled = a.filter(
        (b) =>
          b.status === "cancelled" &&
          prevStatus.current.has(b.id) &&
          prevStatus.current.get(b.id) !== "cancelled"
      );
      if (!firstLoad.current) {
        fresh.forEach((b) => toast(`📅 תור חדש: ${b.customer_name}`));
        justCancelled.forEach((b) => toast(`❌ תור בוטל: ${b.customer_name}`));
        if (fresh.length) setUnseenList((prev) => [...fresh, ...prev]); // newest first
      }
      a.forEach((b) => { seenIds.current.add(b.id); prevStatus.current.set(b.id, b.status); });
      firstLoad.current = false;

      setAppts(a); setSlots(sl); setServices(sv); setStaff(st); setOverrides(ov);
      setErr(null);
    } catch (e) {
      console.error("[dashboard] load failed:", e.message || e, e);
      setErr(e.message || "טעינת הנתונים נכשלה");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    let unsub = () => {};
    try {
      unsub = data.subscribeShop(shop.id, reload);
    } catch (e) {
      console.error("[dashboard] realtime subscribe failed:", e.message || e);
    }
    return () => unsub();
  }, [shop.id]);

  // Shared confirmation modal for sensitive actions.
  const [confirmState, setConfirmState] = useState(null);
  const confirm = (opts) => setConfirmState(opts);

  const selectTab = (k) => { setTab(k); };
  const clearUnseen = () => { setUnseenList([]); setNotifOpen(false); };
  // Tapping a notification jumps to that booking's day in the Calendar.
  const gotoBooking = (b) => {
    setNotifOpen(false);
    setUnseenList([]);
    setTab("calendar");
  };
  const unseen = unseenList.length;

  const common = { shop, appts, slots, services, staff, overrides, reload, confirm };
  return html`
    <div class="min-h-screen pt-16 pb-24 max-w-[480px] mx-auto">
      <${AppBar}
        title=${shop.name}
        right=${html`<button onClick=${() => setNotifOpen((o) => !o)} class="relative w-9 h-9 rounded-full bg-surface-2 border border-border-light flex items-center justify-center text-text-secondary">
          <${Icon} name="notifications" fill=${unseen > 0} className=${unseen > 0 ? "text-primary" : ""} />
          ${unseen > 0 && html`<span class="absolute -top-1 -left-1 min-w-[18px] h-[18px] px-1 rounded-full bg-danger text-white text-[10px] font-bold flex items-center justify-center">${unseen}</span>`}
        </button>`}
      />
      <${NotificationsPanel} open=${notifOpen} items=${unseenList}
        onClose=${() => setNotifOpen(false)} onClear=${clearUnseen} onGoto=${gotoBooking} />
      ${loading
        ? html`<div class="flex justify-center pt-24"><${Spinner} className="text-primary text-3xl" /></div>`
        : err
        ? html`<div class="px-5 pt-24 flex flex-col items-center text-center gap-4">
            <${Icon} name="error" className="text-danger text-4xl" />
            <p class="text-text-secondary">טעינת הנתונים נכשלה</p>
            <p class="text-text-muted text-xs mono">${err}</p>
            <${Btn} variant="gold" onClick=${() => { setLoading(true); reload(); }} className="px-6">נסה שוב</${Btn}>
          </div>`
        : html`<div class="px-5 pt-6">
            ${tab === "calendar" && html`<${CalendarTab} ...${common} />`}
            ${tab === "loyalty" && html`<${LoyaltyTab} appts=${appts} shop=${shop} />`}
            ${tab === "stats" && html`<${StatsTab} appts=${appts} staff=${staff} />`}
            ${tab === "staff" && html`<${StaffTab} ...${common} />`}
            ${tab === "services" && html`<${ServicesTab} ...${common} />`}
            ${tab === "settings" && html`<${SettingsTab} shop=${shop} onSignOut=${onSignOut} confirm=${confirm} reload=${reload} onShopUpdated=${onShopUpdated} />`}
          </div>`}
      <${BottomNav} tabs=${TABS} active=${tab} onSelect=${selectTab} />
      <${ConfirmModal} state=${confirmState} onClose=${() => setConfirmState(null)} />
    </div>
  `;
}

// Bell dropdown: the unseen new-booking alerts. Tap an item to jump to it.
function NotificationsPanel({ open, items, onClose, onClear, onGoto }) {
  if (!open) return null;
  return html`<div class="fixed inset-0 z-50" onClick=${onClose}>
    <div class="absolute top-[60px] left-3 right-3 max-w-[460px] mx-auto bg-surface-container border border-border-light rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] p-3"
         onClick=${(e) => e.stopPropagation()}>
      <div class="flex justify-between items-center mb-2 px-1">
        <h3 class="font-bold">התראות</h3>
        ${items.length > 0 && html`<button onClick=${onClear} class="text-primary text-xs">סמן הכל כנקרא</button>`}
      </div>
      ${items.length === 0
        ? html`<p class="text-text-muted text-sm text-center py-6">אין התראות חדשות</p>`
        : html`<div class="flex flex-col gap-2 max-h-[60vh] overflow-y-auto">
            ${items.map((b) => html`<button key=${b.id} onClick=${() => onGoto(b)}
              class="w-full text-right bg-surface-1 border border-border-light rounded-xl p-3 flex items-center gap-3 hover:bg-surface-2 transition-colors">
              <div class="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center text-primary shrink-0">
                <${Icon} name="event_available" className="text-[20px]" /></div>
              <div class="flex-1 text-right min-w-0">
                <p class="font-bold text-sm truncate">תור חדש · ${b.customer_name}</p>
                <p class="text-text-muted text-xs truncate">${b.slot?.service_name || ""}${b.slot?.slot_time ? " · " + fmtTime(b.slot.slot_time) : ""}</p>
              </div>
              <${Icon} name="chevron_left" className="text-text-muted shrink-0" />
            </button>`)}
          </div>`}
    </div>
  </div>`;
}

// Confirmation dialog. state: { title, body, danger, confirmLabel, onYes }.
function ConfirmModal({ state, onClose }) {
  const [busy, setBusy] = useState(false);
  if (!state) return null;
  const yes = async () => {
    setBusy(true);
    try { await state.onYes?.(); } finally { setBusy(false); onClose(); }
  };
  return html`<${Modal} open=${true} onClose=${busy ? () => {} : onClose} title=${state.title || "אישור פעולה"}>
    <p class="text-text-secondary mb-6">${state.body}</p>
    <div class="flex gap-3">
      <${Btn} variant="ghost" onClick=${onClose} className="flex-1">ביטול</${Btn}>
      <${Btn} variant=${state.danger ? "danger" : "gold"} onClick=${yes} loading=${busy} className="flex-1">
        ${state.confirmLabel || "אישור"}
      </${Btn}>
    </div>
  </${Modal}>`;
}

// ── Calendar / appointments (Stitch _14) ─────────────────────────────────────
function CalendarTab({ shop, appts, slots, services, staff, overrides, reload, confirm }) {
  const [day, setDay] = useState(ymd(new Date()));
  const [staffFilter, setStaffFilter] = useState("all");
  const [addOpen, setAddOpen] = useState(false);
  const [blockOpen, setBlockOpen] = useState(false);
  const activeStaff = staff.filter((m) => m.is_active);
  const activeServices = services.filter((s) => s.is_active);

  const dayOverrides = (overrides || []).filter((o) => o.date === day);
  // Is a slot time inside one of the day's overrides? (local HH:MM compare)
  const timeBlocked = (iso, staffId) => {
    const hhmm = new Date(iso).toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit", hour12: false });
    return dayOverrides.some(
      (o) =>
        (o.staff_id == null || o.staff_id === staffId) &&
        (o.all_day || (hhmm >= (o.start_time || "").slice(0, 5) && hhmm < (o.end_time || "").slice(0, 5)))
    );
  };
  const delOverride = (o) => confirm({
    title: "הסרת חסימה", body: "להסיר את חסימת הזמינות?", danger: true,
    onYes: async () => { await data.deleteOverride(o.id); reload(); },
  });

  const week = useMemo(() => {
    const out = [];
    const base = new Date();
    for (let i = 0; i < 7; i++) {
      const d = new Date(base); d.setDate(base.getDate() + i); out.push(d);
    }
    return out;
  }, []);

  const matchStaff = (sid) => staffFilter === "all" || sid === staffFilter;

  // Unified day timeline: booked appointments + free slots, sorted by time.
  const items = useMemo(() => {
    const booked = appts
      .filter((a) => ymd(new Date(a.slot.slot_time)) === day && matchStaff(a.slot.staff_id))
      .map((a) => ({ kind: "booked", time: a.slot.slot_time, id: a.id,
        title: `${a.slot.service_name} · ${a.customer_name}`, sub: a.customer_phone,
        name: a.customer_name, phone: a.customer_phone, price: slotPrice(a.slot), status: a.status }));
    const free = slots
      .filter((s) => s.status === "free" && ymd(new Date(s.slot_time)) === day && matchStaff(s.staff_id))
      .map((s) => ({ kind: "free", time: s.slot_time, id: s.id, title: s.service_name,
        price: s.price, staff_id: s.staff_id, is_deal: s.is_deal, deal_price: s.deal_price }));
    return [...booked, ...free].sort((x, y) => new Date(x.time) - new Date(y.time));
  }, [appts, slots, day, staffFilter]);

  const dayBooked = items.filter((i) => i.kind === "booked");
  // Cancelled bookings stay visible on the timeline but don't earn revenue.
  const revenue = dayBooked
    .filter((i) => i.status !== "cancelled")
    .reduce((s, i) => s + (Number(i.price) || 0), 0);

  const delSlot = (id) => confirm({
    title: "מחיקת תור פנוי", body: "למחוק את התור הפנוי הזה?", danger: true,
    onYes: async () => { await data.deleteSlot(id); reload(); },
  });

  return html`
    <!-- staff filter -->
    <section class="mb-6 overflow-x-auto no-scrollbar">
      <div class="flex gap-4 min-w-max pb-1">
        <button onClick=${() => setStaffFilter("all")} class="flex flex-col items-center gap-1.5">
          <div class="w-14 h-14 rounded-full flex items-center justify-center ${staffFilter === "all"
            ? "bg-primary shadow-[0_0_15px_rgba(239,178,0,0.3)] text-on-primary"
            : "bg-surface-2 border border-border-light text-text-muted"}">
            <${Icon} name="group" fill=${true} /></div>
          <span class="text-xs ${staffFilter === "all" ? "text-primary" : "text-text-muted"}">הכל</span>
        </button>
        ${activeStaff.map((m) => html`<button key=${m.id} onClick=${() => setStaffFilter(m.id)}
          class="flex flex-col items-center gap-1.5 ${staffFilter === m.id ? "" : "opacity-60"}">
          <div class="w-14 h-14 rounded-full flex items-center justify-center border ${staffFilter === m.id
            ? "border-primary text-primary" : "border-border-light text-text-muted"} bg-surface-2">
            <${Icon} name="person" fill=${true} /></div>
          <span class="text-xs">${m.name}</span>
        </button>`)}
      </div>
    </section>

    <!-- week day picker -->
    <section class="mb-6 overflow-x-auto no-scrollbar">
      <div class="flex gap-2 min-w-max pb-1">
        ${week.map((d) => {
          const key = ymd(d);
          const on = key === day;
          return html`<button key=${key} onClick=${() => setDay(key)}
            class="flex flex-col items-center w-14 h-16 rounded-xl justify-center ${on
              ? "bg-primary text-on-primary ring-1 ring-primary shadow-[0_0_20px_rgba(239,178,0,0.15)]"
              : "border border-border-light text-text-secondary"}">
            <span class="text-xs mb-1">${["א'","ב'","ג'","ד'","ה'","ו'","ש'"][d.getDay()]}</span>
            <span class="mono text-lg font-bold">${d.getDate()}</span>
          </button>`;
        })}
      </div>
    </section>

    <!-- summary tiles -->
    <section class="grid grid-cols-3 gap-3 mb-6">
      ${[["תורים", dayBooked.length], ["פנויים", items.length - dayBooked.length], ["הכנסות", `₪${revenue}`]].map(
        ([l, v], i) => html`<div key=${i} class="bg-surface-1 rounded-xl p-4 flex flex-col items-center border border-border-light">
          <span class="mono text-headline-sm text-xl ${i === 2 ? "text-primary" : ""}">${v}</span>
          <span class="text-xs text-text-muted mt-1">${l}</span>
        </div>`
      )}
    </section>

    <${Btn} variant="dashedGold" onClick=${() => setAddOpen(true)} className="w-full mb-6">
      <${Icon} name="add" /> הוסף תור פנוי
    </${Btn}>

    <!-- timeline -->
    <section class="flex flex-col gap-3 relative">
      ${items.length === 0 && html`<p class="text-center text-text-muted py-10">אין תורים ביום זה</p>`}
      ${items.map((it) => {
        const blocked = it.kind === "free" && timeBlocked(it.time, it.staff_id);
        const wa = it.kind === "booked" && it.phone
          ? waLink(it.phone, `שלום ${it.name}, בנוגע לתורך ב-${shop.name}`)
          : null;
        const cancelled = it.kind === "booked" && it.status === "cancelled";
        return html`<div key=${it.kind + it.id} class="flex items-start gap-3 ${blocked || cancelled ? "opacity-50" : ""}">
        <div class="w-[46px] pt-4 text-left flex-shrink-0 mono text-sm text-text-muted">${fmtTime(it.time)}</div>
        <div class="w-2 h-2 rounded-full mt-5 ${cancelled ? "bg-danger" : it.kind === "booked" ? "bg-info" : "bg-primary/40"}"></div>
        <div class="flex-1 bg-surface-2 border ${cancelled ? "border-danger/30" : it.kind === "booked" ? "border-info/30" : "border-border-light"} rounded-xl p-4">
          <div class="flex justify-between items-start gap-2">
            <h3 class="font-bold ${cancelled ? "line-through" : ""}">${it.title}</h3>
            <div class="flex items-center gap-2 shrink-0">
              ${it.kind === "free" && it.is_deal && it.deal_price != null
                && html`<span class="px-2 py-0.5 rounded bg-primary/10 text-primary text-xs font-bold">🔥 דיל</span>`}
              ${wa && !cancelled && html`<a href=${wa} target="_blank" rel="noopener" class="text-success" title="WhatsApp"><${Icon} name="chat" className="text-[20px]" /></a>`}
              ${it.kind === "booked"
                ? cancelled
                  ? html`<span class="px-2 py-0.5 rounded bg-danger/10 text-danger text-xs">בוטל</span>`
                  : html`<span class="px-2 py-0.5 rounded bg-info/10 text-info text-xs">מוזמן</span>`
                : blocked
                ? html`<span class="px-2 py-0.5 rounded bg-surface-3 text-text-muted text-xs">חסום</span>`
                : html`<button onClick=${() => delSlot(it.id)} class="text-text-muted hover:text-danger"><${Icon} name="delete" className="text-[18px]" /></button>`}
            </div>
          </div>
          <div class="flex items-center gap-2 text-text-muted mono text-sm mt-1" dir="rtl">
            ${it.sub && html`<span dir="ltr">${it.sub}</span>`}
            ${it.sub && html`<span>·</span>`}
            ${it.kind === "free" && it.is_deal && it.deal_price != null
              ? html`<span class="text-primary font-bold">₪${it.deal_price}</span>
                     <span class="line-through text-text-muted/70">₪${it.price}</span>`
              : html`<span class="text-primary">${it.price != null ? "₪" + it.price : "—"}</span>`}
          </div>
        </div>
      </div>`;
      })}
    </section>

    <!-- Availability overrides (blocked dates/hours) -->
    <section class="mt-8">
      <div class="flex justify-between items-center mb-3">
        <h3 class="font-bold text-text-secondary">חסימת זמינות</h3>
        <button onClick=${() => setBlockOpen(true)} class="text-primary text-sm flex items-center gap-1">
          <${Icon} name="event_busy" className="text-[18px]" /> חסום תאריך/שעות
        </button>
      </div>
      ${dayOverrides.length === 0
        ? html`<p class="text-text-muted text-sm">אין חסימות ביום זה.</p>`
        : html`<div class="flex flex-col gap-2">${dayOverrides.map((o) => html`<div key=${o.id}
            class="flex items-center justify-between bg-surface-1 border border-border-light rounded-xl px-3 py-2">
            <div class="flex items-center gap-2 text-sm">
              <${Icon} name="block" className="text-danger text-[18px]" />
              <span>${o.all_day ? "כל היום" : `${(o.start_time || "").slice(0, 5)}–${(o.end_time || "").slice(0, 5)}`}</span>
              ${o.note && html`<span class="text-text-muted">· ${o.note}</span>`}
            </div>
            <button onClick=${() => delOverride(o)} class="text-text-muted hover:text-danger"><${Icon} name="delete" className="text-[18px]" /></button>
          </div>`)}</div>`}
    </section>

    <${AddSlotModal} open=${addOpen} onClose=${() => setAddOpen(false)} shop=${shop}
      services=${activeServices} staff=${activeStaff} day=${day} timeBlocked=${timeBlocked}
      onSaved=${() => { setAddOpen(false); reload(); }} />
    <${AddBlockModal} open=${blockOpen} onClose=${() => setBlockOpen(false)} shop=${shop}
      staff=${activeStaff} day=${day} onSaved=${() => { setBlockOpen(false); reload(); }} />
  `;
}

function AddSlotModal({ open, onClose, shop, services, staff, day, timeBlocked, onSaved }) {
  const [svc, setSvc] = useState("");
  const [time, setTime] = useState("10:00");
  const [staffId, setStaffId] = useState("");
  const [isDeal, setIsDeal] = useState(false);
  const [dealPrice, setDealPrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const save = async () => {
    const service = services.find((s) => s.id === svc) || services[0];
    if (!service) { setErr("הוסף שירות קודם בלשונית שירותים"); return; }
    const slot_time = new Date(`${day}T${time}:00`).toISOString();
    if (timeBlocked && timeBlocked(slot_time, staffId || null)) {
      setErr("הזמן הזה חסום ביומן — הסר את החסימה או בחר שעה אחרת"); return;
    }
    let deal_price = null;
    if (isDeal) {
      deal_price = Number(dealPrice);
      if (!deal_price || deal_price <= 0) { setErr("יש להזין מחיר מבצע תקין"); return; }
      if (service.price != null && deal_price >= service.price) {
        setErr("מחיר המבצע חייב להיות נמוך מהמחיר הרגיל"); return;
      }
    }
    setBusy(true); setErr("");
    try {
      await data.createSlot(shop.id, {
        service_name: service.name, price: service.price, slot_time,
        staff_id: staffId || null,
        is_deal: isDeal, deal_price,
      });
      onSaved();
    } catch (e) { setErr(e.message || "שמירה נכשלה"); setBusy(false); }
  };

  return html`<${Modal} open=${open} onClose=${onClose} title="הוסף תור פנוי">
    <div class="flex flex-col gap-4">
      ${err && html`<p class="text-danger text-sm">${err}</p>`}
      <label class="flex flex-col gap-2"><span class="text-sm text-text-secondary">שירות</span>
        <select value=${svc} onChange=${(e) => setSvc(e.target.value)}
          class="bg-surface-2 border border-border-light rounded-xl px-4 py-3 focus:outline-none focus:border-primary">
          ${services.length === 0 && html`<option value="">— אין שירותים —</option>`}
          ${services.map((s) => html`<option key=${s.id} value=${s.id}>${s.name} · ₪${s.price ?? "—"}</option>`)}
        </select></label>
      <${Field} label="שעה" type="time" value=${time} onInput=${(e) => setTime(e.target.value)} dir="ltr" />
      <label class="flex flex-col gap-2"><span class="text-sm text-text-secondary">ספר (אופציונלי)</span>
        <select value=${staffId} onChange=${(e) => setStaffId(e.target.value)}
          class="bg-surface-2 border border-border-light rounded-xl px-4 py-3 focus:outline-none focus:border-primary">
          <option value="">— ללא —</option>
          ${staff.map((m) => html`<option key=${m.id} value=${m.id}>${m.name}</option>`)}
        </select></label>

      <!-- Last-minute deal: flag this slot + set a reduced price. -->
      <button onClick=${() => setIsDeal(!isDeal)} type="button"
        class="flex items-center justify-between bg-surface-1 border border-border-light rounded-xl px-4 py-3">
        <span class="flex items-center gap-2">🔥 סמן כדיל של הרגע האחרון</span>
        <span class="w-12 h-7 rounded-full p-1 transition-colors ${isDeal ? "bg-primary" : "bg-surface-variant"}">
          <span class="block w-5 h-5 rounded-full bg-white transition-transform ${isDeal ? "translate-x-0" : "translate-x-5"}"></span>
        </span>
      </button>
      ${isDeal && html`<${Field} label="מחיר מבצע ₪" type="number" value=${dealPrice}
        onInput=${(e) => setDealPrice(e.target.value)} dir="ltr" placeholder="מחיר מוזל" />`}

      <${Btn} variant="gold" onClick=${save} loading=${busy} className="w-full">הוסף תור (${day})</${Btn}>
    </div>
  </${Modal}>`;
}

// Block a date / time window so customers can't book it.
function AddBlockModal({ open, onClose, shop, staff, day, onSaved }) {
  const [allDay, setAllDay] = useState(true);
  const [start, setStart] = useState("12:00");
  const [end, setEnd] = useState("14:00");
  const [staffId, setStaffId] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const save = async () => {
    if (!allDay && start >= end) { setErr("שעת הסיום חייבת להיות אחרי ההתחלה"); return; }
    setBusy(true); setErr("");
    try {
      await data.createOverride(shop.id, {
        date: day, all_day: allDay,
        start_time: allDay ? null : start, end_time: allDay ? null : end,
        staff_id: staffId || null, note: note || null,
      });
      onSaved();
    } catch (e) { setErr(e.message || "שמירה נכשלה"); setBusy(false); }
  };
  return html`<${Modal} open=${open} onClose=${onClose} title=${`חסימת זמינות · ${day}`}>
    <div class="flex flex-col gap-4">
      ${err && html`<p class="text-danger text-sm">${err}</p>`}
      <button onClick=${() => setAllDay(!allDay)} class="flex items-center justify-between bg-surface-1 border border-border-light rounded-xl px-4 py-3">
        <span>חסימת יום שלם</span>
        <span class="w-12 h-7 rounded-full p-1 transition-colors ${allDay ? "bg-primary" : "bg-surface-variant"}">
          <span class="block w-5 h-5 rounded-full bg-white transition-transform ${allDay ? "translate-x-0" : "translate-x-5"}"></span>
        </span>
      </button>
      ${!allDay && html`<div class="flex gap-3">
        <${Field} label="מ-" type="time" value=${start} onInput=${(e) => setStart(e.target.value)} dir="ltr" class="flex-1" />
        <${Field} label="עד" type="time" value=${end} onInput=${(e) => setEnd(e.target.value)} dir="ltr" class="flex-1" />
      </div>`}
      <label class="flex flex-col gap-2"><span class="text-sm text-text-secondary">ספר (אופציונלי — ברירת מחדל: כל המספרה)</span>
        <select value=${staffId} onChange=${(e) => setStaffId(e.target.value)}
          class="bg-surface-2 border border-border-light rounded-xl px-4 py-3 focus:outline-none focus:border-primary">
          <option value="">כל המספרה</option>
          ${staff.map((m) => html`<option key=${m.id} value=${m.id}>${m.name}</option>`)}
        </select></label>
      <${Field} label="הערה (אופציונלי)" value=${note} onInput=${(e) => setNote(e.target.value)} placeholder="חופשה / אירוע" />
      <${Btn} variant="gold" onClick=${save} loading=${busy} className="w-full">חסום</${Btn}>
    </div>
  </${Modal}>`;
}

// ── Client Loyalty ───────────────────────────────────────────────────────────
function LoyaltyTab({ appts, shop }) {
  const [sort, setSort] = useState("visits"); // visits | recent | spend
  const clients = useMemo(() => {
    const map = {};
    appts.forEach((a) => {
      const phone = (a.customer_phone || "").trim() || "ללא טלפון";
      const c = map[phone] || (map[phone] = { phone, name: a.customer_name, visits: 0, spend: 0, last: 0 });
      c.visits += 1;
      c.spend += Number(slotPrice(a.slot)) || 0;
      const t = new Date(a.slot?.slot_time || a.created_at).getTime();
      if (t > c.last) { c.last = t; c.name = a.customer_name; }
    });
    const arr = Object.values(map);
    arr.sort((x, y) =>
      sort === "spend" ? y.spend - x.spend : sort === "recent" ? y.last - x.last : y.visits - x.visits
    );
    return arr;
  }, [appts, sort]);

  const sorts = [["visits", "ביקורים"], ["recent", "אחרון"], ["spend", "הוצאה"]];
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-4">לקוחות</h2>
    <div class="flex flex-row-reverse bg-surface-3 rounded-xl p-1 border border-border-light mb-5">
      ${sorts.map(([k, l]) => html`<button key=${k} onClick=${() => setSort(k)}
        class="flex-1 py-1.5 rounded-lg text-sm ${sort === k ? "bg-surface-1 text-primary font-bold" : "text-text-muted"}">${l}</button>`)}
    </div>
    ${clients.length === 0
      ? html`<p class="text-text-muted text-center py-10">אין עדיין לקוחות</p>`
      : html`<div class="flex flex-col gap-3">${clients.map((c) => {
          const wa = waLink(c.phone, `שלום ${c.name}`);
          return html`<div key=${c.phone} class="bg-surface-2 rounded-xl p-4 border border-border-light">
          <div class="flex justify-between items-center mb-2">
            <div class="flex items-center gap-2">
              <div class="w-9 h-9 rounded-full bg-surface-3 flex items-center justify-center text-primary"><${Icon} name="person" fill=${true} /></div>
              <div><h3 class="font-bold">${c.name || "לקוח"}</h3>
                <p class="text-text-muted mono text-xs" dir="ltr">${c.phone}</p></div>
            </div>
            ${wa && html`<button onClick=${() => window.open(wa, "_blank", "noopener")} title="WhatsApp"
              class="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center text-success active:scale-95 transition-transform">
              <${Icon} name="chat" /></button>`}
          </div>
          <div class="grid grid-cols-3 gap-2 text-center">
            <div><span class="block mono font-bold">${c.visits}</span><span class="text-[11px] text-text-muted">ביקורים</span></div>
            <div><span class="block mono font-bold text-primary">₪${c.spend}</span><span class="text-[11px] text-text-muted">סה"כ</span></div>
            <div><span class="block mono text-sm">${c.last ? new Date(c.last).toLocaleDateString("he-IL", { day: "numeric", month: "short" }) : "—"}</span><span class="text-[11px] text-text-muted">אחרון</span></div>
          </div>
        </div>`;
        })}</div>`}
  `;
}

// ── Services (Stitch _18) ────────────────────────────────────────────────────
function ServicesTab({ shop, services, reload, confirm }) {
  const [edit, setEdit] = useState(null); // service object or {} for new
  const del = (s) => confirm({
    title: "מחיקת שירות", body: `למחוק את "${s.name}"? לא ניתן לבטל.`, danger: true,
    onYes: async () => { await data.deleteService(s.id); reload(); },
  });
  const toggle = async (s) => { await data.updateService(s.id, { is_active: !s.is_active }); reload(); };
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-4">שירותים</h2>
    <div class="flex flex-col gap-3">
      ${services.length === 0 && html`<p class="text-text-muted text-center py-8">אין שירותים עדיין</p>`}
      ${services.map((s) => html`<div key=${s.id} class="bg-surface-2 rounded-xl p-4 border border-border-light flex flex-col gap-3 ${s.is_active ? "" : "opacity-60"}">
        <div class="flex justify-between items-start">
          <div class="flex items-start gap-3">
            <span class="text-2xl">✂️</span>
            <div><h3 class="font-bold flex items-center gap-2">${s.name}
              ${!s.is_active && html`<span class="text-[10px] px-1.5 py-0.5 rounded bg-surface-3 text-text-muted">לא פעיל</span>`}</h3>
              <p class="text-text-muted mono text-xs mt-0.5">${s.category || ""}</p></div>
          </div>
          <div class="flex items-center gap-2">
            <button onClick=${() => toggle(s)} title="פעיל/לא פעיל"
              class="w-11 h-6 rounded-full p-1 transition-colors ${s.is_active ? "bg-primary" : "bg-surface-variant"}">
              <span class="block w-4 h-4 rounded-full bg-white transition-transform ${s.is_active ? "translate-x-0" : "translate-x-5"}"></span>
            </button>
            <button onClick=${() => setEdit(s)} class="w-9 h-9 rounded-lg bg-surface-3 flex items-center justify-center text-primary/80"><${Icon} name="edit" className="text-[18px]" /></button>
            <button onClick=${() => del(s)} class="w-9 h-9 rounded-lg bg-surface-3 flex items-center justify-center text-danger/80"><${Icon} name="delete" className="text-[18px]" /></button>
          </div>
        </div>
        <div class="h-px bg-border-light"></div>
        <div class="flex justify-between items-center mono text-sm">
          <span class="text-text-muted flex items-center gap-1"><${Icon} name="schedule" className="text-[16px]" /> ${s.duration_mins ?? "—"} דק'</span>
          <span class="text-price-lg text-primary" dir="ltr">₪${s.price ?? "—"}</span>
        </div>
      </div>`)}
      <${Btn} variant="dashedGold" onClick=${() => setEdit({})} className="w-full"><${Icon} name="add" /> הוסף שירות</${Btn}>
    </div>
    <${ServiceModal} shop=${shop} service=${edit} onClose=${() => setEdit(null)} onSaved=${() => { setEdit(null); reload(); }} />
  `;
}

function ServiceModal({ shop, service, onClose, onSaved }) {
  const [f, setF] = useState({ name: "", price: "", duration_mins: "", category: "" });
  useEffect(() => { if (service) setF({ name: service.name || "", price: service.price ?? "", duration_mins: service.duration_mins ?? "", category: service.category || "" }); }, [service]);
  const [busy, setBusy] = useState(false);
  if (!service) return null;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    if (!f.name.trim()) return;
    setBusy(true);
    const patch = { name: f.name.trim(), price: Number(f.price) || null, duration_mins: Number(f.duration_mins) || null, category: f.category || null };
    try {
      if (service.id) await data.updateService(service.id, patch);
      else await data.createService(shop.id, { ...patch, staff_id: null });
      onSaved();
    } finally { setBusy(false); }
  };
  return html`<${Modal} open=${!!service} onClose=${onClose} title=${service.id ? "עריכת שירות" : "שירות חדש"}>
    <div class="flex flex-col gap-4">
      <${Field} label="שם" value=${f.name} onInput=${set("name")} placeholder="תספורת גברים" />
      <div class="flex gap-3">
        <${Field} label="מחיר ₪" type="number" value=${f.price} onInput=${set("price")} dir="ltr" class="flex-1" />
        <${Field} label="דקות" type="number" value=${f.duration_mins} onInput=${set("duration_mins")} dir="ltr" class="flex-1" />
      </div>
      <${Field} label="קטגוריה (אופציונלי)" value=${f.category} onInput=${set("category")} />
      <${Btn} variant="gold" onClick=${save} loading=${busy} className="w-full">שמור</${Btn}>
    </div>
  </${Modal}>`;
}

// ── Employees (Stitch _3) ────────────────────────────────────────────────────
function StaffTab({ shop, staff, reload, confirm }) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const toggle = async (m) => { await data.updateStaff(m.id, { is_active: !m.is_active }); reload(); };
  const del = (m) => confirm({
    title: "מחיקת עובד", body: `למחוק את "${m.name}"? לא ניתן לבטל.`, danger: true,
    onYes: async () => { await data.deleteStaff(m.id); reload(); },
  });
  const add = async () => { if (!name.trim()) return; await data.createStaff(shop.id, name.trim()); setName(""); setAdding(false); reload(); };
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-4">ניהול עובדים</h2>
    <div class="bg-surface-1 border border-border-light rounded-xl overflow-hidden">
      ${staff.length === 0 && html`<p class="text-text-muted text-center py-8">אין עובדים עדיין</p>`}
      ${staff.map((m) => html`<div key=${m.id} class="p-4 border-b border-border-light last:border-0 flex items-center justify-between ${m.is_active ? "" : "opacity-60"}">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-full bg-surface-2 border-2 ${m.is_active ? "border-primary" : "border-border-light"} flex items-center justify-center text-primary">
            <${Icon} name="person" fill=${true} /></div>
          <div><h3 class="font-bold">${m.name}</h3>
            <p class="text-text-muted mono text-xs">${m.is_active ? "פעיל" : "לא פעיל"}</p></div>
        </div>
        <div class="flex items-center gap-2">
          <button onClick=${() => toggle(m)}
            class="w-12 h-7 rounded-full p-1 transition-colors ${m.is_active ? "bg-primary" : "bg-surface-variant"}">
            <span class="block w-5 h-5 rounded-full bg-white transition-transform ${m.is_active ? "translate-x-0" : "translate-x-5"}"></span>
          </button>
          <button onClick=${() => del(m)} class="w-8 h-8 rounded-full bg-surface-2 border border-border-light flex items-center justify-center text-text-muted hover:text-danger"><${Icon} name="delete" className="text-[18px]" /></button>
        </div>
      </div>`)}
    </div>
    ${adding
      ? html`<div class="mt-4 flex gap-2">
          <${Field} value=${name} onInput=${(e) => setName(e.target.value)} placeholder="שם הספר" class="flex-1" />
          <${Btn} variant="gold" onClick=${add} className="px-5">הוסף</${Btn}>
        </div>`
      : html`<${Btn} variant="dashedGold" onClick=${() => setAdding(true)} className="w-full mt-4"><${Icon} name="add" /> הוסף עובד</${Btn}>`}
  `;
}

// ── Statistics (Stitch _23) ──────────────────────────────────────────────────
function StatsTab({ appts, staff }) {
  const [period, setPeriod] = useState(30);
  const [staffFilter, setStaffFilter] = useState("all"); // "all" | staff id
  const activeStaff = (staff || []).filter((m) => m.is_active);

  const stats = useMemo(() => {
    const since = Date.now() - period * 86400000;
    const inRange = appts.filter(
      (a) =>
        new Date(a.created_at).getTime() >= since &&
        (staffFilter === "all" || a.slot?.staff_id === staffFilter)
    );
    const revenue = inRange.reduce((s, a) => s + (Number(slotPrice(a.slot)) || 0), 0);
    const visitBuckets = {};
    const revBuckets = {};
    inRange.forEach((a) => {
      const k = ymd(new Date(a.created_at));
      revBuckets[k] = (revBuckets[k] || 0) + (Number(slotPrice(a.slot)) || 0);
      visitBuckets[k] = (visitBuckets[k] || 0) + 1;
    });
    const days = Object.keys(revBuckets).sort();
    return {
      revenue,
      visits: inRange.length,
      avg: inRange.length ? Math.round(revenue / inRange.length) : 0,
      revSeries: days.map((k) => revBuckets[k]),
      visitSeries: days.map((k) => visitBuckets[k]),
    };
  }, [appts, period, staffFilter]);

  const periods = [[30, "חודש"], [90, "3 ח'"], [180, "6 ח'"], [365, "שנה"], [99999, "הכל"]];
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-4">סטטיסטיקות</h2>

    <!-- Staff selector -->
    <section class="mb-5 overflow-x-auto no-scrollbar">
      <div class="flex gap-4 min-w-max pb-1">
        <button onClick=${() => setStaffFilter("all")} class="flex flex-col items-center gap-1.5">
          <div class="w-14 h-14 rounded-full flex items-center justify-center ${staffFilter === "all"
            ? "bg-primary shadow-[0_0_15px_rgba(239,178,0,0.3)] text-on-primary"
            : "bg-surface-2 border border-border-light text-text-muted"}">
            <${Icon} name="group" fill=${true} /></div>
          <span class="text-xs ${staffFilter === "all" ? "text-primary" : "text-text-muted"}">הכל</span>
        </button>
        ${activeStaff.map((m) => html`<button key=${m.id} onClick=${() => setStaffFilter(m.id)}
          class="flex flex-col items-center gap-1.5 ${staffFilter === m.id ? "" : "opacity-60"}">
          <div class="w-14 h-14 rounded-full flex items-center justify-center border ${staffFilter === m.id
            ? "border-primary text-primary" : "border-border-light text-text-muted"} bg-surface-2">
            <${Icon} name="person" fill=${true} /></div>
          <span class="text-xs">${m.name}</span>
        </button>`)}
      </div>
    </section>

    <!-- Period filter -->
    <div class="flex flex-row-reverse bg-surface-3 rounded-xl p-1 border border-border-light mb-5">
      ${periods.map(([d, l]) => html`<button key=${l} onClick=${() => setPeriod(d)}
        class="flex-1 py-1.5 rounded-lg text-sm ${period === d ? "bg-surface-1 text-primary font-bold" : "text-text-muted"}">${l}</button>`)}
    </div>

    <!-- Summary tiles -->
    <div class="grid grid-cols-3 gap-3 mb-5">
      ${[["הכנסות", `₪${stats.revenue.toLocaleString()}`, "text-primary"], ["תורים", stats.visits, ""], ["ממוצע", `₪${stats.avg}`, ""]].map(
        ([l, v, c], i) => html`<div key=${i} class="bg-surface-1 rounded-xl p-3 flex flex-col items-center border border-border-light">
          <span class="text-lg font-extrabold ${c}">${v}</span><span class="text-[11px] text-text-muted mt-1">${l}</span></div>`
      )}
    </div>

    <article class="bg-surface-2 rounded-xl p-5 border border-border-light mb-4">
      <h3 class="text-text-secondary text-sm mb-1">הכנסות</h3>
      <div class="flex items-baseline gap-1" dir="ltr"><span class="text-text-muted">₪</span>
        <span class="text-4xl font-extrabold">${stats.revenue.toLocaleString()}</span></div>
      <${Chart} values=${stats.revSeries} color="#34C759" />
    </article>
    <article class="bg-surface-2 rounded-xl p-5 border border-border-light">
      <h3 class="text-text-secondary text-sm mb-1">מספר תורים</h3>
      <span class="text-4xl font-extrabold">${stats.visits}</span>
      <${Chart} values=${stats.visitSeries} color="#0A84FF" line />
    </article>
  `;
}

function Chart({ values, color, line = false }) {
  const w = 360, h = 90;
  if (!values || values.length === 0)
    return html`<div class="h-[90px] flex items-center justify-center text-text-muted text-sm mt-2">אין נתונים בטווח</div>`;
  const max = Math.max(...values, 1);
  const pts = values.length === 1 ? [values[0], values[0]] : values;
  const step = w / (pts.length - 1);
  const coords = pts.map((v, i) => [i * step, h - (v / max) * (h - 10) - 5]);
  const path = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c[0].toFixed(1)},${c[1].toFixed(1)}`).join(" ");
  const area = `${path} L${w},${h} L0,${h} Z`;
  return html`<svg viewBox="0 0 ${w} ${h}" class="w-full h-[90px] mt-3 overflow-visible">
    ${!line && html`<path d=${area} fill=${color} fill-opacity="0.15" />`}
    <path d=${path} fill="none" stroke=${color} stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx=${coords[coords.length - 1][0]} cy=${coords[coords.length - 1][1]} r="4" fill=${color} />
  </svg>`;
}

// ── Settings (Stitch _41) ────────────────────────────────────────────────────
function SettingsTab({ shop, onSignOut, confirm, reload, onShopUpdated }) {
  const [pwOpen, setPwOpen] = useState(false);
  const [bizOpen, setBizOpen] = useState(false);
  const rows = [
    ["store", "פרטי העסק", shop.name, () => setBizOpen(true)],
    ["lock", "שינוי סיסמה", "דורש אימות מחדש", () => setPwOpen(true)],
    ["payments", "אמצעי תשלום", "חשבון בנק", null],
    ["language", "שפה", "עברית", null],
  ];
  const signOut = () => confirm({
    title: "התנתקות", body: "להתנתק מהחשבון?", confirmLabel: "התנתק", onYes: onSignOut,
  });
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-4">הגדרות</h2>
    <div class="flex flex-col gap-3">
      ${rows.map(([icon, title, sub, onClick]) => html`<button key=${title} onClick=${onClick || (() => {})}
        class="w-full flex items-center justify-between p-4 bg-surface-2 rounded-xl border border-border-light ${onClick ? "active:scale-[0.99]" : "opacity-70"}">
        <div class="flex items-center gap-4">
          <div class="w-11 h-11 rounded-lg bg-surface-3 flex items-center justify-center text-primary"><${Icon} name=${icon} /></div>
          <div class="text-right"><h3 class="font-bold">${title}</h3>
            ${sub && html`<p class="text-text-muted text-sm">${sub}</p>`}</div>
        </div>
        <${Icon} name="chevron_left" className="text-text-muted" />
      </button>`)}
      <${Btn} variant="danger" onClick=${signOut} className="w-full mt-4"><${Icon} name="logout" /> התנתקות</${Btn}>
    </div>
    <${ChangePasswordModal} open=${pwOpen} onClose=${() => setPwOpen(false)} />
    <${BizInfoModal} open=${bizOpen} shop=${shop} onClose=${() => setBizOpen(false)}
      onSaved=${(updated) => { setBizOpen(false); onShopUpdated?.(updated); reload(); }} />
  `;
}

// Edit core business details (name, address, phone, opening hours). Pre-filled
// from `shop`; on save persists via updateShop and hands the fresh row back so
// the dashboard (AppBar title etc.) reflects the change immediately.
const BIZ_DAY_LABELS = ["א'", "ב'", "ג'", "ד'", "ה'", "ו'", "ש'"];
const BIZ_DAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

function BizInfoModal({ open, shop, onClose, onSaved }) {
  const [f, setF] = useState({ name: "", address: "", phone: "" });
  const [hours, setHours] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) return;
    setF({ name: shop.name || "", address: shop.address || "", phone: shop.phone || "" });
    // Seed every day with a full {open, close, closed} shape, overlaying whatever
    // the shop already has so partial/legacy opening_hours objects still edit.
    const seeded = BIZ_DAY_KEYS.reduce((a, k) => {
      a[k] = { open: "09:00", close: "19:00", closed: k === "sat", ...(shop.opening_hours?.[k] || {}) };
      return a;
    }, {});
    setHours(seeded);
    setErr("");
  }, [open, shop]);

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const setDay = (k, patch) => setHours({ ...hours, [k]: { ...hours[k], ...patch } });

  const save = async () => {
    if (!f.name.trim()) { setErr("יש להזין שם עסק"); return; }
    setBusy(true); setErr("");
    try {
      const updated = await data.updateShop(shop.id, {
        name: f.name.trim(),
        address: f.address.trim() || null,
        phone: f.phone.trim() || null,
        opening_hours: hours,
      });
      toast("הפרטים עודכנו ✓");
      onSaved(updated);
    } catch (e) { setErr(e.message || "העדכון נכשל"); setBusy(false); }
  };

  if (!open) return null;
  return html`<${Modal} open=${true} onClose=${onClose} title="פרטי העסק">
    <div class="flex flex-col gap-4">
      ${err && html`<p class="text-danger text-sm">${err}</p>`}
      <${Field} label="שם העסק" value=${f.name} onInput=${set("name")} placeholder="שם המספרה" />
      <${Field} label="כתובת" value=${f.address} onInput=${set("address")} placeholder="רחוב, עיר" />
      <${Field} label="טלפון" value=${f.phone} onInput=${set("phone")} placeholder="05X-XXXXXXX" dir="ltr" />
      <div>
        <span class="text-sm text-text-secondary">שעות פעילות</span>
        <div class="mt-2 flex flex-col gap-2">
          ${BIZ_DAY_KEYS.map((k, i) => html`<div key=${k}
            class="flex items-center gap-3 bg-surface-1 border border-border-light rounded-xl px-3 py-2">
            <span class="w-6 text-center font-bold">${BIZ_DAY_LABELS[i]}</span>
            ${hours[k]?.closed
              ? html`<span class="flex-1 text-text-muted text-sm">סגור</span>`
              : html`<div class="flex-1 flex items-center gap-2 mono text-sm" dir="ltr">
                  <input type="time" value=${hours[k]?.open || "09:00"}
                    onInput=${(e) => setDay(k, { open: e.target.value })}
                    class="bg-surface-2 border border-border-light rounded px-2 py-1" />
                  <span>—</span>
                  <input type="time" value=${hours[k]?.close || "19:00"}
                    onInput=${(e) => setDay(k, { close: e.target.value })}
                    class="bg-surface-2 border border-border-light rounded px-2 py-1" />
                </div>`}
            <button type="button" onClick=${() => setDay(k, { closed: !hours[k]?.closed })}
              class="text-xs ${hours[k]?.closed ? "text-primary" : "text-text-muted"}">
              ${hours[k]?.closed ? "פתח" : "סגור"}
            </button>
          </div>`)}
        </div>
      </div>
      <${Btn} variant="gold" onClick=${save} loading=${busy} className="w-full">שמור</${Btn}>
    </div>
  </${Modal}>`;
}

// Sensitive account change: requires re-authentication with the current password.
function ChangePasswordModal({ open, onClose }) {
  const [cur, setCur] = useState("");
  const [nw, setNw] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const save = async () => {
    if (nw.length < 6) { setErr("הסיסמה החדשה חייבת להכיל לפחות 6 תווים"); return; }
    setBusy(true); setErr("");
    try {
      await auth.reauthenticate(cur); // verify current password (re-auth)
      await auth.updatePassword(nw);
      toast("הסיסמה עודכנה ✓");
      setCur(""); setNw("");
      onClose();
    } catch (e) {
      setErr(e.message || "העדכון נכשל");
    } finally {
      setBusy(false);
    }
  };
  if (!open) return null;
  return html`<${Modal} open=${true} onClose=${onClose} title="שינוי סיסמה">
    <div class="flex flex-col gap-4">
      <p class="text-text-muted text-sm">לאבטחת החשבון, יש לאמת את הסיסמה הנוכחית.</p>
      ${err && html`<p class="text-danger text-sm">${err}</p>`}
      <${Field} label="סיסמה נוכחית" type="password" value=${cur} onInput=${(e) => setCur(e.target.value)} dir="ltr" />
      <${Field} label="סיסמה חדשה" type="password" value=${nw} onInput=${(e) => setNw(e.target.value)} dir="ltr" />
      <${Btn} variant="gold" onClick=${save} loading=${busy} className="w-full">אמת ושמור</${Btn}>
    </div>
  </${Modal}>`;
}
