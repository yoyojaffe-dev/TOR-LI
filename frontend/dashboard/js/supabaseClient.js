// Authenticated Supabase client for the barber dashboard. persistSession keeps
// the barber logged in across reloads; all reads/writes run under the barber's
// auth (owner RLS) — never the service role.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { config } from "./config.js";

export const supabase = createClient(config.SUPABASE_URL, config.SUPABASE_ANON_KEY, {
  auth: { persistSession: true, autoRefreshToken: true },
});
