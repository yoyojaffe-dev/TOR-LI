// Barber dashboard root: auth gate → onboarding (no shop) or dashboard (has shop).
import { html, useState, useEffect, useRef, createRoot, Icon, Field, Btn, Spinner } from "./ui.js";
import * as auth from "./auth.js";
import { getMyShop } from "./data.js";
import { Onboarding } from "./onboarding.js";
import { Dashboard } from "./dashboard.js";

function AuthScreen() {
  const [mode, setMode] = useState("login"); // login | signup
  const [f, setF] = useState({ email: "", password: "", name: "", phone: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async () => {
    if (!f.email || !f.password) { setErr("יש למלא אימייל וסיסמה"); return; }
    setBusy(true); setErr("");
    try {
      const res =
        mode === "login"
          ? await auth.signIn(f.email, f.password)
          : await auth.signUp(f.email, f.password, f.name, f.phone);
      if (res?.error) throw res.error;
      // onAuthChange in App drives the transition.
    } catch (e) {
      setErr(e.message || "אירעה שגיאה");
      setBusy(false);
    }
  };

  return html`
    <div class="min-h-screen max-w-[480px] mx-auto px-6 flex flex-col justify-center">
      <div class="flex flex-col items-center mb-8">
        <div class="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/30 flex items-center justify-center text-primary mb-3">
          <${Icon} name="content_cut" fill=${true} className="text-3xl" />
        </div>
        <h1 class="text-3xl font-extrabold">Tor-li לעסקים</h1>
        <p class="text-text-secondary text-sm mt-1">ניהול המספרה שלך</p>
      </div>
      ${err && html`<p class="text-danger text-sm mb-3 text-center">${err}</p>`}
      <div class="flex flex-col gap-3">
        ${mode === "signup" && html`<${Field} label="שם מלא" value=${f.name} onInput=${set("name")} placeholder="ישראל ישראלי" />`}
        <${Field} label="אימייל" type="email" value=${f.email} onInput=${set("email")} placeholder="barber@example.com" dir="ltr" />
        ${mode === "signup" && html`<${Field} label="טלפון" value=${f.phone} onInput=${set("phone")} placeholder="05X-XXXXXXX" dir="ltr" />`}
        <${Field} label="סיסמה" type="password" value=${f.password} onInput=${set("password")} placeholder="••••••••" dir="ltr" />
        <${Btn} variant="gold" onClick=${submit} loading=${busy} className="w-full mt-2">
          ${mode === "login" ? "התחברות" : "יצירת חשבון"}
        </${Btn}>
      </div>
      <button onClick=${() => { setMode(mode === "login" ? "signup" : "login"); setErr(""); }}
        class="text-primary text-sm mt-5 mx-auto">
        ${mode === "login" ? "אין לך חשבון? הרשמה" : "כבר יש לך חשבון? התחברות"}
      </button>
    </div>
  `;
}

function Center({ children }) {
  return html`<div class="min-h-screen flex items-center justify-center">${children}</div>`;
}

function App() {
  const [session, setSession] = useState(undefined); // undefined=loading, null=out
  const [shop, setShop] = useState(undefined);
  const lastUserId = useRef(undefined); // last authenticated user id we acted on

  useEffect(() => {
    auth.getSession().then((s) => { lastUserId.current = s?.user?.id ?? null; setSession(s); });
    const { data: sub } = auth.onAuthChange((event, s) => {
      // Always keep the session/token current.
      setSession(s);
      // Reset the shop (which unmounts/remounts Dashboard) ONLY when the
      // authenticated identity actually changes — a real sign-out (id -> null)
      // or a different user. supabase-js re-broadcasts SIGNED_IN on cross-tab
      // localStorage session sync with the SAME user id; those must be ignored,
      // or every other tab's focus tears down Dashboard's realtime + state.
      const newId = s?.user?.id ?? null;
      const identityChanged = newId !== lastUserId.current;
      lastUserId.current = newId;
      if (identityChanged) {
        setShop(undefined);
      }
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session) { setShop(undefined); return; }
    getMyShop().then(setShop).catch(() => setShop(null));
  }, [session?.user?.id]);

  const signOut = async () => { await auth.signOut(); };

  if (session === undefined) return html`<${Center}><${Spinner} className="text-primary text-3xl" /></${Center}>`;
  if (session === null) return html`<${AuthScreen} />`;
  if (shop === undefined) return html`<${Center}><${Spinner} className="text-primary text-3xl" /></${Center}>`;
  if (shop === null) return html`<${Onboarding} onComplete=${setShop} />`;
  return html`<${Dashboard} shop=${shop} onSignOut=${signOut} />`;
}

createRoot(document.getElementById("root")).render(html`<${App} />`);
