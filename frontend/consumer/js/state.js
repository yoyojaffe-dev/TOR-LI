// Minimal observable state store for the consumer app.

function createStore(initial) {
  let state = { ...initial };
  const listeners = new Set();

  return {
    get: () => state,
    set(patch) {
      state = { ...state, ...patch };
      listeners.forEach((fn) => fn(state));
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}

const SESSION_KEY = "torli_session";
const DEVICE_KEY = "torli_device_id";

// A GoTrue session (access + refresh JWTs) issued after phone-OTP login.
// Replaces the old anonymous `torli_user_token`: identity is now verified and
// every booking/review request is authorized with the access token.
function loadSession() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY)) || null;
  } catch {
    return null;
  }
}

// A stable per-browser id used only for non-auth keying (e.g. avatar filenames),
// so those keep working before the user logs in.
function getDeviceId() {
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

export const store = createStore({
  position: null, // { lat, lng }
  barbershops: [],
  selectedBarbershop: null,
  slots: [],
  activeLock: null, // { slotId, lockedUntil }
  session: loadSession(), // { access_token, refresh_token, expires_at, user_id }
  deviceId: getDeviceId(),
});

// ── Session helpers ──────────────────────────────────────────────────────────

export function getSession() {
  return store.get().session;
}

export function setSession(session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  store.set({ session });
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  store.set({ session: null });
}
