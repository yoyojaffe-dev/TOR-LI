// Consumer auth: phone (SMS) OTP login via the backend /auth endpoints.
// Identity is a real GoTrue session (replacing the old anonymous user_token):
// booking, cancelling, and reviewing all require a logged-in session.
import { api } from "./api.js";
import { getSession, setSession, clearSession } from "./state.js";

export function isLoggedIn() {
  const s = getSession();
  return !!s?.access_token;
}

export function logout() {
  clearSession();
}

// Resolve true when a session exists, otherwise open the OTP modal and resolve
// true on successful login / false if the user dismisses it.
export function ensureLoggedIn() {
  if (isLoggedIn()) return Promise.resolve(true);
  return openLoginModal();
}

function openLoginModal() {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.dir = "rtl";
    backdrop.className =
      "fixed inset-0 z-[120] bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center";
    backdrop.innerHTML = `
      <div class="bg-surface-1 w-full sm:max-w-sm rounded-t-3xl sm:rounded-3xl border border-border-light p-gutter pb-8 flex flex-col gap-4">
        <div class="flex items-center justify-between">
          <h2 class="font-headline-sm text-lg">התחברות</h2>
          <button data-close class="material-symbols-outlined text-text-muted">close</button>
        </div>

        <div data-step="phone" class="flex flex-col gap-3">
          <p class="font-body-md text-text-secondary text-sm">הזן מספר טלפון ונשלח לך קוד אימות ב-SMS.</p>
          <input data-phone type="tel" inputmode="tel" placeholder="050-000-0000"
                 class="w-full h-12 rounded-xl bg-surface-2 border border-border-light px-4 text-right
                        font-body-lg outline-none focus:border-primary" />
          <button data-send
                  class="w-full h-12 rounded-xl bg-primary text-on-primary font-body-md active:scale-95 transition-transform">
            שלח קוד
          </button>
        </div>

        <div data-step="code" class="hidden flex-col gap-3">
          <p class="font-body-md text-text-secondary text-sm">הזן את הקוד שקיבלת ב-SMS.</p>
          <input data-code type="text" inputmode="numeric" maxlength="6" placeholder="------"
                 class="w-full h-12 rounded-xl bg-surface-2 border border-border-light px-4 text-center tracking-[0.5em]
                        font-body-lg outline-none focus:border-primary" />
          <button data-verify
                  class="w-full h-12 rounded-xl bg-primary text-on-primary font-body-md active:scale-95 transition-transform">
            אמת והתחבר
          </button>
          <button data-resend class="font-label-mono text-label-mono text-primary text-sm">שלח קוד שוב</button>
        </div>

        <p data-err class="hidden font-body-md text-error text-sm text-center"></p>
      </div>`;

    const $ = (sel) => backdrop.querySelector(sel);
    const stepPhone = $("[data-step='phone']");
    const stepCode = $("[data-step='code']");
    const errEl = $("[data-err]");
    let phone = "";
    let done = false;

    const showError = (msg) => {
      errEl.textContent = msg;
      errEl.classList.remove("hidden");
    };
    const clearError = () => errEl.classList.add("hidden");

    const close = (result) => {
      if (done) return;
      done = true;
      backdrop.remove();
      resolve(result);
    };

    const send = async () => {
      clearError();
      phone = $("[data-phone]").value.trim();
      if (!phone) return showError("נא להזין מספר טלפון");
      const btn = $("[data-send]");
      btn.disabled = true;
      btn.textContent = "שולח...";
      try {
        await api.sendOtp(phone);
        stepPhone.classList.add("hidden");
        stepCode.classList.remove("hidden");
        stepCode.classList.add("flex");
        $("[data-code]").focus();
      } catch (err) {
        showError(err?.status === 429 ? "יותר מדי בקשות — נסה שוב בעוד רגע" : "שליחת הקוד נכשלה");
      } finally {
        btn.disabled = false;
        btn.textContent = "שלח קוד";
      }
    };

    const verify = async () => {
      clearError();
      const code = $("[data-code]").value.trim();
      if (!code) return showError("נא להזין את הקוד");
      const btn = $("[data-verify]");
      btn.disabled = true;
      btn.textContent = "מאמת...";
      try {
        const session = await api.verifyOtp(phone, code);
        setSession(session);
        close(true);
      } catch {
        showError("קוד שגוי או שפג תוקפו");
        btn.disabled = false;
        btn.textContent = "אמת והתחבר";
      }
    };

    $("[data-close]").addEventListener("click", () => close(false));
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) close(false);
    });
    $("[data-send]").addEventListener("click", send);
    $("[data-verify]").addEventListener("click", verify);
    $("[data-resend]").addEventListener("click", send);

    document.body.appendChild(backdrop);
    $("[data-phone]").focus();
  });
}
