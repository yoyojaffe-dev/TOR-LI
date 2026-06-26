// Fetch wrappers around the FastAPI backend.
import { config } from "./config.js";

async function request(path, options = {}) {
  const res = await fetch(`${config.BACKEND_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
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

  // Location radius search (PostGIS). Returns nearest-first barbershops.
  nearbyBarbershops: (lat, lng, radius = config.DEFAULT_RADIUS_M) =>
    request(`/barbershops?lat=${lat}&lng=${lng}&radius=${radius}`),

  getBarbershop: (id) => request(`/barbershops/${id}`),

  listSlots: (barbershopId, onlyFree = true) =>
    request(`/slots?barbershop_id=${barbershopId}&only_free=${onlyFree}`),

  realtimeInfo: () => request("/slots/realtime-info"),

  // A user's booking history (joined with slot + shop detail).
  listBookings: (userToken) =>
    request(`/bookings?user_token=${encodeURIComponent(userToken)}`),

  cancelBooking: (bookingId, userToken) =>
    request("/bookings/cancel", {
      method: "POST",
      body: JSON.stringify({ booking_id: bookingId, user_token: userToken }),
    }),

  // Pessimistic lock lifecycle.
  lockSlot: (slotId, userToken) =>
    request("/bookings/lock", {
      method: "POST",
      body: JSON.stringify({ slot_id: slotId, user_token: userToken }),
    }),

  releaseSlot: (slotId, userToken) =>
    request("/bookings/release", {
      method: "POST",
      body: JSON.stringify({ slot_id: slotId, user_token: userToken }),
    }),

  confirmBooking: (slotId, userToken, customerName, customerPhone) =>
    request("/bookings/confirm", {
      method: "POST",
      body: JSON.stringify({
        slot_id: slotId,
        user_token: userToken,
        customer_name: customerName,
        customer_phone: customerPhone,
      }),
    }),
};
