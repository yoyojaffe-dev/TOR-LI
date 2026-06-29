// Booking flow: lock -> visible countdown -> confirm (or auto-release on expiry).
import { api } from "./api.js";
import { ensureLoggedIn } from "./auth.js";
import { store } from "./state.js";

let countdownTimer = null;

// Sentinel thrown when the user dismisses the login prompt instead of booking.
export class LoginRequiredError extends Error {}

// Step 1: lock the slot. Starts a countdown; calls callbacks each tick / on expiry.
export async function startBooking(slotId, { onTick, onExpire } = {}) {
  // Booking requires a verified phone session — prompt for OTP login if needed.
  if (!(await ensureLoggedIn())) throw new LoginRequiredError("login required");
  const lock = await api.lockSlot(slotId); // throws ApiError(409) if taken
  const lockedUntil = new Date(lock.locked_until).getTime();
  store.set({ activeLock: { slotId, lockedUntil } });

  clearInterval(countdownTimer);
  countdownTimer = setInterval(() => {
    const remaining = Math.max(0, Math.round((lockedUntil - Date.now()) / 1000));
    if (onTick) onTick(remaining);
    if (remaining <= 0) {
      clearInterval(countdownTimer);
      store.set({ activeLock: null });
      if (onExpire) onExpire();
    }
  }, 1000);

  return lock;
}

// Step 2: confirm. Triggers the backend Booking Agent + flips the slot to booked.
export async function confirmBooking(customerName, customerPhone) {
  const { activeLock } = store.get();
  if (!activeLock) throw new Error("No active lock to confirm");
  const result = await api.confirmBooking(activeLock.slotId, customerName, customerPhone);
  clearInterval(countdownTimer);
  store.set({ activeLock: null });
  return result;
}

// Cancel: release the lock early.
export async function cancelBooking() {
  const { activeLock } = store.get();
  clearInterval(countdownTimer);
  if (activeLock) {
    await api.releaseSlot(activeLock.slotId);
    store.set({ activeLock: null });
  }
}
