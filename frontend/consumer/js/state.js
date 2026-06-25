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

// A stable per-browser token identifies who holds a pessimistic lock.
function getUserToken() {
  let token = localStorage.getItem("torli_user_token");
  if (!token) {
    token = crypto.randomUUID();
    localStorage.setItem("torli_user_token", token);
  }
  return token;
}

export const store = createStore({
  position: null, // { lat, lng }
  barbershops: [],
  selectedBarbershop: null,
  slots: [],
  activeLock: null, // { slotId, lockedUntil }
  userToken: getUserToken(),
});
