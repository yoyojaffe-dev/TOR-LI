// Barber onboarding — 5 Stitch steps: business+hours → services → staff →
// payment → sync. On finish, creates the shop + services + staff under owner RLS.
import { html, useState, Icon, Field, Btn, AppBar, ProgressBar } from "./ui.js";
import * as data from "./data.js";

const DAYS = ["א'", "ב'", "ג'", "ד'", "ה'", "ו'", "ש'"];
const DAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const BANKS = ["לאומי", "הפועלים", "דיסקונט", "מזרחי טפחות", "הבינלאומי"];
const SYNC_OPTIONS = [
  { key: "none", icon: "block", label: "ניהול ידני", sub: "אני אנהל את היומן כאן" },
  { key: "api", icon: "language", label: "חיבור לאתר המספרה", sub: "סנכרון אוטומטי מ-API" },
  { key: "gcal", icon: "calendar_month", label: "Google Calendar", sub: "סנכרון יומן" },
];

export function Onboarding({ onComplete }) {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [biz, setBiz] = useState({ name: "", address: "", phone: "", lat: null, lng: null });
  const [hours, setHours] = useState(
    DAY_KEYS.reduce((a, k) => ((a[k] = { open: "09:00", close: "19:00", closed: k === "sat" }), a), {})
  );
  const [services, setServices] = useState([{ name: "תספורת גברים", duration_mins: 30, price: 60 }]);
  const [staff, setStaff] = useState([]);
  const [bank, setBank] = useState({ bank: "", branch: "", account: "" });
  const [sync, setSync] = useState("none");

  const total = 5;
  const next = () => setStep((s) => Math.min(s + 1, total - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  const finish = async () => {
    if (!biz.name.trim()) { setStep(0); setErr("יש להזין שם עסק"); return; }
    if (!biz.address.trim()) { setStep(0); setErr("יש להזין כתובת עסק"); return; }
    setBusy(true); setErr("");
    try {
      // Resolve the typed address to coordinates so the shop has a PostGIS
      // location and shows up in the consumer's nearby search.
      let lat, lng;
      try {
        ({ lat, lng } = await data.geocodeAddress(biz.address.trim()));
      } catch {
        setStep(0); setErr("לא הצלחנו לאתר את כתובת העסק — בדוק/י את הכתובת");
        setBusy(false); return;
      }
      const shop = await data.createShop({
        name: biz.name.trim(), address: biz.address.trim(), phone: biz.phone,
        lat, lng, opening_hours: hours,
      });
      for (const s of services) {
        if (s.name.trim()) await data.createService(shop.id, {
          name: s.name.trim(), duration_mins: Number(s.duration_mins) || null,
          price: Number(s.price) || null, category: null, staff_id: null,
        });
      }
      for (const m of staff) if (m.name.trim()) await data.createStaff(shop.id, m.name.trim());
      onComplete(shop);
    } catch (e) {
      setErr(e.message || "יצירת העסק נכשלה");
      setBusy(false);
    }
  };

  return html`
    <div class="min-h-screen pt-16 pb-28 max-w-[480px] mx-auto">
      <${AppBar}
        title="הקמת עסק"
        left=${step > 0 && html`<button onClick=${back}><${Icon} name="arrow_forward" /></button>`}
      />
      <div class="px-5 pt-4"><${ProgressBar} step=${step + 1} total=${total} /></div>
      <div class="px-5 pt-6">
        ${err && html`<p class="text-danger text-sm mb-4">${err}</p>`}
        ${step === 0 && html`<${StepBusiness} biz=${biz} setBiz=${setBiz} hours=${hours} setHours=${setHours} />`}
        ${step === 1 && html`<${StepServices} services=${services} setServices=${setServices} />`}
        ${step === 2 && html`<${StepStaff} staff=${staff} setStaff=${setStaff} />`}
        ${step === 3 && html`<${StepBank} bank=${bank} setBank=${setBank} />`}
        ${step === 4 && html`<${StepSync} sync=${sync} setSync=${setSync} />`}
      </div>

      <div class="fixed bottom-0 inset-x-0 max-w-[480px] mx-auto p-5 bg-background/90 backdrop-blur-xl border-t border-border-light">
        ${step < total - 1
          ? html`<${Btn} variant="primary" onClick=${next} className="w-full">המשך</${Btn}>`
          : html`<${Btn} variant="gold" onClick=${finish} loading=${busy} className="w-full">סיום והפעלת עסק</${Btn}>`}
      </div>
    </div>
  `;
}

function StepBusiness({ biz, setBiz, hours, setHours }) {
  const set = (k) => (e) => setBiz({ ...biz, [k]: e.target.value });
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-2">פרטי העסק</h2>
    <p class="text-text-secondary text-sm mb-6">הפרטים יוצגו ללקוחות באפליקציה.</p>
    <div class="flex flex-col gap-4">
      <${Field} label="שם המספרה" value=${biz.name} onInput=${set("name")} placeholder="הכנס את שם המספרה" />
      <${Field} label="כתובת" value=${biz.address} onInput=${set("address")} placeholder="רחוב, עיר" />
      <${Field} label="טלפון" value=${biz.phone} onInput=${set("phone")} placeholder="05X-XXXXXXX" dir="ltr" />

      <div class="mt-2">
        <span class="text-body-md text-text-secondary text-sm">שעות פעילות</span>
        <div class="mt-2 flex flex-col gap-2">
          ${DAY_KEYS.map(
            (k, i) => html`<div key=${k} class="flex items-center gap-3 bg-surface-1 border border-border-light rounded-xl px-3 py-2">
              <span class="w-6 text-center font-bold">${DAYS[i]}</span>
              ${hours[k].closed
                ? html`<span class="flex-1 text-text-muted text-sm">סגור</span>`
                : html`<div class="flex-1 flex items-center gap-2 mono text-sm" dir="ltr">
                    <input type="time" value=${hours[k].open}
                      onInput=${(e) => setHours({ ...hours, [k]: { ...hours[k], open: e.target.value } })}
                      class="bg-surface-2 border border-border-light rounded px-2 py-1" />
                    <span>—</span>
                    <input type="time" value=${hours[k].close}
                      onInput=${(e) => setHours({ ...hours, [k]: { ...hours[k], close: e.target.value } })}
                      class="bg-surface-2 border border-border-light rounded px-2 py-1" />
                  </div>`}
              <button onClick=${() => setHours({ ...hours, [k]: { ...hours[k], closed: !hours[k].closed } })}
                class="text-xs ${hours[k].closed ? "text-primary" : "text-text-muted"}">
                ${hours[k].closed ? "פתח" : "סגור"}
              </button>
            </div>`
          )}
        </div>
      </div>
    </div>
  `;
}

function StepServices({ services, setServices }) {
  const add = () => setServices([...services, { name: "", duration_mins: 30, price: 50 }]);
  const upd = (i, k, v) => setServices(services.map((s, j) => (j === i ? { ...s, [k]: v } : s)));
  const rm = (i) => setServices(services.filter((_, j) => j !== i));
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-2">שירותים ומחירים</h2>
    <p class="text-text-secondary text-sm mb-6">הוסף את התפריט של המספרה.</p>
    <div class="flex flex-col gap-3">
      ${services.map(
        (s, i) => html`<div key=${i} class="bg-surface-1 border border-border-light rounded-xl p-3 flex flex-col gap-2">
          <div class="flex items-center gap-2">
            <input value=${s.name} placeholder="שם השירות" onInput=${(e) => upd(i, "name", e.target.value)}
              class="flex-1 bg-surface-2 border border-border-light rounded-lg px-3 py-2 focus:outline-none focus:border-primary" />
            <button onClick=${() => rm(i)} class="text-text-muted hover:text-danger"><${Icon} name="delete" /></button>
          </div>
          <div class="flex gap-2 mono text-sm" dir="ltr">
            <div class="flex items-center gap-1 bg-surface-2 border border-border-light rounded-lg px-2">
              <${Icon} name="schedule" className="text-[16px] text-text-muted" />
              <input type="number" value=${s.duration_mins} onInput=${(e) => upd(i, "duration_mins", e.target.value)}
                class="w-14 bg-transparent py-2 focus:outline-none" /> <span class="text-text-muted">דק'</span>
            </div>
            <div class="flex items-center gap-1 bg-surface-2 border border-border-light rounded-lg px-2">
              <span class="text-primary">₪</span>
              <input type="number" value=${s.price} onInput=${(e) => upd(i, "price", e.target.value)}
                class="w-16 bg-transparent py-2 text-primary focus:outline-none" />
            </div>
          </div>
        </div>`
      )}
      <${Btn} variant="dashedGold" onClick=${add}><${Icon} name="add" /> הוסף שירות</${Btn}>
    </div>
  `;
}

function StepStaff({ staff, setStaff }) {
  const add = () => setStaff([...staff, { name: "" }]);
  const upd = (i, v) => setStaff(staff.map((m, j) => (j === i ? { name: v } : m)));
  const rm = (i) => setStaff(staff.filter((_, j) => j !== i));
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-2">צוות</h2>
    <p class="text-text-secondary text-sm mb-6">הוסף את הספרים בצוות (אפשר לדלג).</p>
    <div class="flex flex-col gap-3">
      ${staff.map(
        (m, i) => html`<div key=${i} class="bg-surface-1 border border-border-light rounded-xl p-3 flex items-center gap-3">
          <div class="w-10 h-10 rounded-full bg-surface-container border border-border-light flex items-center justify-center text-text-muted">
            <${Icon} name="person" fill=${true} />
          </div>
          <input value=${m.name} placeholder="למשל: ירון כהן" onInput=${(e) => upd(i, e.target.value)}
            class="flex-1 bg-surface-2 border border-border-light rounded-lg px-3 py-2 focus:outline-none focus:border-primary" />
          <button onClick=${() => rm(i)} class="text-text-muted hover:text-danger"><${Icon} name="delete" /></button>
        </div>`
      )}
      <${Btn} variant="dashedGold" onClick=${add}><${Icon} name="add" /> הוסף ספר</${Btn}>
    </div>
  `;
}

function StepBank({ bank, setBank }) {
  const set = (k) => (e) => setBank({ ...bank, [k]: e.target.value });
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-2">פרטי תשלום</h2>
    <p class="text-text-secondary text-sm mb-6">לקבלת תשלומים מהלקוחות.</p>
    <div class="flex flex-col gap-4">
      <label class="flex flex-col gap-2">
        <span class="text-sm text-text-secondary">שם הבנק</span>
        <select value=${bank.bank} onChange=${set("bank")}
          class="bg-surface-2 border border-border-light rounded-xl px-4 py-3 focus:outline-none focus:border-primary">
          <option value="">בחר בנק...</option>
          ${BANKS.map((b) => html`<option key=${b} value=${b}>${b}</option>`)}
        </select>
      </label>
      <${Field} label="מספר סניף" value=${bank.branch} onInput=${set("branch")} placeholder="123" dir="ltr" />
      <${Field} label="מספר חשבון" value=${bank.account} onInput=${set("account")} placeholder="12345678" dir="ltr" />
      <div class="flex items-center gap-2 text-text-muted text-xs mt-2">
        <${Icon} name="lock" className="text-[16px]" /> הפרטים מאובטחים ומוצפנים.
      </div>
    </div>
  `;
}

function StepSync({ sync, setSync }) {
  return html`
    <h2 class="text-headline-md text-2xl font-extrabold mb-2">סנכרון יומן</h2>
    <p class="text-text-secondary text-sm mb-6">איך תרצה לנהל את התורים?</p>
    <div class="flex flex-col gap-3">
      ${SYNC_OPTIONS.map(
        (o) => html`<button key=${o.key} onClick=${() => setSync(o.key)}
          class="w-full bg-surface-2 border rounded-xl p-4 flex items-center justify-between transition-all
                 ${sync === o.key ? "border-primary" : "border-border-light"}">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-full bg-surface-container flex items-center justify-center text-primary">
              <${Icon} name=${o.icon} />
            </div>
            <div class="text-right">
              <h3 class="text-body-lg font-bold">${o.label}</h3>
              <p class="text-text-muted text-sm">${o.sub}</p>
            </div>
          </div>
          <${Icon} name=${sync === o.key ? "radio_button_checked" : "radio_button_unchecked"}
            className=${sync === o.key ? "text-primary" : "text-text-muted"} />
        </button>`
      )}
    </div>
  `;
}
