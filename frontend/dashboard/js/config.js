// Management dashboard configuration (mirrors consumer config).
// Production frontend host (Railway): serve from here -> use the production
// backend automatically. window.__TORLI_BACKEND_URL__ override still wins; dev
// falls back to localhost:8000.
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
};
