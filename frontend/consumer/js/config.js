// Tor-li consumer app configuration.
// SUPABASE_ANON_KEY and GOOGLE_MAPS_API_KEY are public client keys (safe to ship).
// Override BACKEND_URL per environment (localhost for dev, Railway URL in prod).

// Production frontend host (Railway). When the app is served from here, talk to
// the production backend automatically. The window.__TORLI_BACKEND_URL__ override
// still wins, and local/dev falls back to localhost:8000.
const PROD_FRONTEND_HOST = "frontend-production-2c43.up.railway.app";
const PROD_BACKEND_URL = "https://tor-li-production.up.railway.app";

export const config = {
  BACKEND_URL:
    window.__TORLI_BACKEND_URL__ ||
    (window.location.hostname === PROD_FRONTEND_HOST
      ? PROD_BACKEND_URL
      : "http://localhost:8000"),
  SUPABASE_URL: "https://ekugfzrmitvoiamevtfa.supabase.co",
  SUPABASE_ANON_KEY:
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVrdWdmenJtaXR2b2lhbWV2dGZhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIyMDU4ODAsImV4cCI6MjA5Nzc4MTg4MH0.ATNqChnGJFXj8SN9g7qr4EhDtms-QRbAEXbDdOkO_iY",
  GOOGLE_MAPS_API_KEY: "AIzaSyDD05RMhEYeM6X58RwHgR3HQEKIG4RVYg8",
  // Pessimistic lock window shown as a countdown in the booking UI (seconds).
  // Mirrors backend slot_lock_ttl_seconds; actual countdown uses the server's
  // locked_until, this is just a UI fallback.
  LOCK_TTL_SECONDS: 300,
  // Default radius for nearby search (metres).
  DEFAULT_RADIUS_M: 2000,
};
