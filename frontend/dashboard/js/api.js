// Dashboard API client (shares the FastAPI backend with the consumer app).
import { config } from "./config.js";

async function request(path, options = {}) {
  const res = await fetch(`${config.BACKEND_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail || res.statusText);
  return res.status === 204 ? null : res.json();
}

export const api = {
  health: () => request("/health"),
  getBarbershop: (id) => request(`/barbershops/${id}`),
  listSlots: (barbershopId, onlyFree = false) =>
    request(`/slots?barbershop_id=${barbershopId}&only_free=${onlyFree}`),
};
