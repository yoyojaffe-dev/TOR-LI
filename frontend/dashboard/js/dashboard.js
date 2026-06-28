// Barber dashboard — 5 tabs (Stitch _14/_23/_3/_18/_41) over live owner data.
import {
  html, useState, useEffect, useMemo, Icon, Btn, Field, AppBar, BottomNav, FAB, Modal,
  Spinner, fmtTime, ymd,
} from "./ui.js";
import * as data from "./data.js";

const TABS = [
  { key: "calendar", label: "לוח", icon: "calendar_month" },
  { key: "stats", label: "סטטיסטיקות", icon: "equalizer" },
  { key: "staff", label: "עובדים", icon: "group" },
  { key: "services", label: "שירותים", icon: "content_cut" },
  { key: "settings", label: "הגדרות", icon: "settings" },
];

export function Dashboard({ shop, onSignOut }) {
  const [tab, setTab] = useState("calendar");
  const [appts, setAppts] = useState([]);
  const [slots, setSlots] = useState([]);
  const [services, setServices] = useState([]);
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  // Load everything; on ANY failure stop the spinner and surface the reason
  // (never leave the dashboard stuck loading).
  const reload = async () => {
    try {
      const [a, sl, sv, st] = await Promise.all([
        data.listAppointments(),
        data.listSlots(shop.id),
        data.listServices(shop.id),
        data.listStaff(shop.id),
      ]);
      setAppts(a); setSlots(sl); setServices(sv); setStaff(st);
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

  const common = { shop, appts, slots, services, staff, reload, confirm };
  return html`
    <div class="min-h-screen pt-16 pb-24 max-w-[480px] mx-auto">
      <${AppBar}
        title=${shop.name}
        right=${html`<div class="w-9 h-9 rounded-full bg-surface-2 border border-primary flex items-center justify-center text-primary">
          <${Icon} name="storefront" fill=${true} className="text-[18px]" /></div>`}
      />
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
            ${tab === "stats" && html`<${StatsTab} appts=${appts} staff=${staff} />`}
            ${tab === "staff" && html`<${StaffTab} ...${common} />`}
            ${tab === "services" && html`<${ServicesTab} ...${common} />`}
            ${tab === "settings" && html`<${SettingsTab} shop=${shop} onSignOut=${onSignOut} confirm=${confirm} reload=${reload} />`}
          </div>`}
      <${BottomNav} tabs=${TABS} active=${tab} onSelect=${setTab} />
      <${ConfirmModal} state=${confirmState} onClose=${() => setConfirmState(null)} />
    </div>
  `;
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
function CalendarTab({ shop, appts, slots, services, staff, reload, confirm }) {
  const [day, setDay] = useState(ymd(new Date()));
  const [staffFilter, setStaffFilter] = useState("all");
  const [addOpen, setAddOpen] = useState(false);
  const activeStaff = staff.filter((m) => m.is_active);
  const activeServices = services.filter((s) => s.is_active);

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
        price: a.slot.price, status: a.status }));
    const free = slots
      .filter((s) => s.status === "free" && ymd(new Date(s.slot_time)) === day && matchStaff(s.staff_id))
      .map((s) => ({ kind: "free", time: s.slot_time, id: s.id, title: s.service_name, price: s.price }));
    return [...booked, ...free].sort((x, y) => new Date(x.time) - new Date(y.time));
  }, [appts, slots, day, staffFilter]);

  const dayBooked = items.filter((i) => i.kind === "booked");
  const revenue = dayBooked.reduce((s, i) => s + (Number(i.price) || 0), 0);

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
      ${items.map((it) => html`<div key=${it.kind + it.id} class="flex items-start gap-3">
        <div class="w-[46px] pt-4 text-left flex-shrink-0 mono text-sm text-text-muted">${fmtTime(it.time)}</div>
        <div class="w-2 h-2 rounded-full mt-5 ${it.kind === "booked" ? "bg-info" : "bg-primary/40"}"></div>
        <div class="flex-1 bg-surface-2 border ${it.kind === "booked" ? "border-info/30" : "border-border-light"} rounded-xl p-4">
          <div class="flex justify-between items-start">
            <h3 class="font-bold">${it.title}</h3>
            ${it.kind === "booked"
              ? html`<span class="px-2 py-0.5 rounded bg-info/10 text-info text-xs">מוזמן</span>`
              : html`<button onClick=${() => delSlot(it.id)} class="text-text-muted hover:text-danger"><${Icon} name="delete" className="text-[18px]" /></button>`}
          </div>
          <div class="flex items-center gap-2 text-text-muted mono text-sm mt-1" dir="rtl">
            ${it.sub && html`<span dir="ltr">${it.sub}</span>`}
            ${it.sub && html`<span>·</span>`}
            <span class="text-primary">${it.price != null ? "₪" + it.price : "—"}</span>
          </div>
        </div>
      </div>`)}
    </section>

    <${AddSlotModal} open=${addOpen} onClose=${() => setAddOpen(false)} shop=${shop}
      services=${activeServices} staff=${activeStaff} day=${day} onSaved=${() => { setAddOpen(false); reload(); }} />
  `;
}

function AddSlotModal({ open, onClose, shop, services, staff, day, onSaved }) {
  const [svc, setSvc] = useState("");
  const [time, setTime] = useState("10:00");
  const [staffId, setStaffId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const save = async () => {
    const service = services.find((s) => s.id === svc) || services[0];
    if (!service) { setErr("הוסף שירות קודם בלשונית שירותים"); return; }
    setBusy(true); setErr("");
    try {
      const slot_time = new Date(`${day}T${time}:00`).toISOString();
      await data.createSlot(shop.id, {
        service_name: service.name, price: service.price, slot_time,
        staff_id: staffId || null,
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
      <${Btn} variant="gold" onClick=${save} loading=${busy} className="w-full">הוסף תור (${day})</${Btn}>
    </div>
  </${Modal}>`;
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
function StatsTab({ appts }) {
  const [period, setPeriod] = useState(30);
  const stats = useMemo(() => {
    const since = Date.now() - period * 86400000;
    const inRange = appts.filter((a) => new Date(a.created_at).getTime() >= since);
    const revenue = inRange.reduce((s, a) => s + (Number(a.slot?.price) || 0), 0);
    // bucket revenue by day for the chart
    const buckets = {};
    inRange.forEach((a) => {
      const k = ymd(new Date(a.created_at));
      buckets[k] = (buckets[k] || 0) + (Number(a.slot?.price) || 0);
    });
    const series = Object.keys(buckets).sort().map((k) => buckets[k]);
    return { revenue, visits: inRange.length, series };
  }, [appts, period]);

  const periods = [[30, "1M"], [90, "3M"], [180, "6M"], [365, "1Y"], [99999, "All"]];
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-4">סטטיסטיקות</h2>
    <div class="flex flex-row-reverse bg-surface-3 rounded-xl p-1 border border-border-light mb-5">
      ${periods.map(([d, l]) => html`<button key=${l} onClick=${() => setPeriod(d)}
        class="flex-1 py-1.5 rounded-lg mono text-sm ${period === d ? "bg-surface-1 text-primary" : "text-text-muted"}">${l}</button>`)}
    </div>
    <article class="bg-surface-2 rounded-xl p-5 border border-border-light mb-4">
      <h3 class="text-text-secondary text-sm mb-1">הכנסות</h3>
      <div class="flex items-baseline gap-1" dir="ltr"><span class="text-text-muted">₪</span>
        <span class="text-4xl font-extrabold">${stats.revenue.toLocaleString()}</span></div>
      <${Chart} values=${stats.series} color="#34C759" />
    </article>
    <article class="bg-surface-2 rounded-xl p-5 border border-border-light">
      <h3 class="text-text-secondary text-sm mb-1">מספר תורים</h3>
      <span class="text-4xl font-extrabold">${stats.visits}</span>
      <${Chart} values=${stats.series.map((v) => (v > 0 ? 1 : 0))} color="#0A84FF" line />
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
function SettingsTab({ shop, onSignOut, confirm, reload }) {
  const rows = [
    ["store", "פרטי העסק", shop.name],
    ["payments", "אמצעי תשלום", "חשבון בנק"],
    ["notifications", "התראות", ""],
    ["language", "שפה", "עברית"],
  ];
  const signOut = () => confirm({
    title: "התנתקות", body: "להתנתק מהחשבון?", confirmLabel: "התנתק", onYes: onSignOut,
  });
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-4">הגדרות</h2>
    <div class="flex flex-col gap-3">
      ${rows.map(([icon, title, sub]) => html`<button key=${title}
        class="w-full flex items-center justify-between p-4 bg-surface-2 rounded-xl border border-border-light">
        <div class="flex items-center gap-4">
          <div class="w-11 h-11 rounded-lg bg-surface-3 flex items-center justify-center text-primary"><${Icon} name=${icon} /></div>
          <div class="text-right"><h3 class="font-bold">${title}</h3>
            ${sub && html`<p class="text-text-muted text-sm">${sub}</p>`}</div>
        </div>
        <${Icon} name="chevron_left" className="text-text-muted" />
      </button>`)}
      <${Btn} variant="danger" onClick=${signOut} className="w-full mt-4"><${Icon} name="logout" /> התנתקות</${Btn}>
    </div>
  `;
}
