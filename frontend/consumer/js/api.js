// Fetch wrappers around the FastAPI backend.
import { config } from "./config.js";
import { getSession } from "./state.js";

async function request(path, options = {}) {
  // Hard timeout so a slow/hung backend (e.g. confirm_booking stalling on the
  // Booking Agent) can NEVER freeze the UI forever — it aborts and surfaces an
  // error that the caller's catch turns into a toast + state reset.
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 25000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  // Authorize with the logged-in user's access token when we have one.
  const session = getSession();
  const authHeader = session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {};
  try {
    const res = await fetch(`${config.BACKEND_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...authHeader,
        ...(options.headers || {}),
      },
      signal: controller.signal,
    });
    if (!res.ok) {
      let detail;
      try {
        detail = (await res.json()).detail;
      } catch {
        detail = res.statusText;
      }
      throw new ApiError(res.status, detail);
    }
    return res.status === 204 ? null : res.json();
  } catch (err) {
    if (err.name === "AbortError") {
      throw new ApiError(0, "פג זמן הבקשה — בדוק חיבור לשרת ונסה שוב");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export const api = {
  health: () => request("/health"),

  // ── Auth: phone (SMS) OTP login ────────────────────────────────────────────
  sendOtp: (phone) =>
    request("/auth/send-otp", { method: "POST", body: JSON.stringify({ phone }) }),

  verifyOtp: (phone, token) =>
    request("/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ phone, token }),
    }),

  // Location radius search (PostGIS). Returns nearest-first barbershops.
  nearbyBarbershops: (lat, lng, radius = config.DEFAULT_RADIUS_M) =>
    request(`/barbershops?lat=${lat}&lng=${lng}&radius=${radius}`),

  getBarbershop: (id) => request(`/barbershops/${id}`),

  listSlots: (barbershopId, onlyFree = true) =>
    request(`/slots?barbershop_id=${barbershopId}&only_free=${onlyFree}`),

  // Free upcoming slots near a point (home "Available Nearby" quick-book).
  nearbySlots: (lat, lng, radius = 5000, limit = 20) =>
    request(`/slots/nearby?lat=${lat}&lng=${lng}&radius=${radius}&limit=${limit}`),

  // All active last-minute deals (NOT distance-capped), nearest first.
  deals: (lat, lng) => request(`/slots/deals?lat=${lat}&lng=${lng}`),

  // Reviews: list for a barbershop (public), submit one for a past booking (auth).
  listReviews: (barbershopId) =>
    request(`/reviews?barbershop_id=${encodeURIComponent(barbershopId)}`),

  submitReview: (bookingId, rating, comment) =>
    request("/reviews", {
      method: "POST",
      body: JSON.stringify({ booking_id: bookingId, rating, comment }),
    }),

  realtimeInfo: () => request("/slots/realtime-info"),

  // The caller's booking history (joined with slot + shop detail). Auth scoped.
  listBookings: () => request("/bookings"),

  cancelBooking: (bookingId) =>
    request("/bookings/cancel", {
      method: "POST",
      body: JSON.stringify({ booking_id: bookingId }),
    }),

  // Pessimistic lock lifecycle (all auth scoped to the caller via auth.uid()).
  lockSlot: (slotId) =>
    request("/bookings/lock", {
      method: "POST",
      body: JSON.stringify({ slot_id: slotId }),
    }),

  releaseSlot: (slotId) =>
    request("/bookings/release", {
      method: "POST",
      body: JSON.stringify({ slot_id: slotId }),
    }),

  confirmBooking: (slotId, customerName, customerPhone) =>
    request("/bookings/confirm", {
      method: "POST",
      body: JSON.stringify({
        slot_id: slotId,
        customer_name: customerName,
        customer_phone: customerPhone,
      }),
    }),
};
