// Supabase client (loaded from CDN as an ES module — no build step).
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { config } from "./config.js";

export const supabase = createClient(
  config.SUPABASE_URL,
  config.SUPABASE_ANON_KEY,
  { realtime: { params: { eventsPerSecond: 10 } } }
);
